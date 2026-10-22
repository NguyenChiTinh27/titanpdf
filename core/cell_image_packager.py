# -*- coding: utf-8 -*-
"""
core/cell_image_packager.py
--------------------------------------------------------------------------------
Enterprise Cell Image Packager for Openpyxl XLSX Spreadsheets.
Injects images directly into Excel / WPS cells using the native DISPIMG mechanism:
- xl/cellimages.xml (<etc:cellImage> / <xdr:pic>)
- xl/_rels/cellimages.xml.rels
- xl/media/image_{i}.{ext}
- updates [Content_Types].xml & xl/_rels/workbook.xml.rels
- updates worksheet XML cell formulas: =_xlfn.DISPIMG("ID_...", 1)
--------------------------------------------------------------------------------
"""

import io
import re
import uuid
import zipfile
from typing import Dict, Any, Optional

def package_cell_images(openpyxl_buf: io.BytesIO, images_by_cell: Dict[str, Dict[str, Any]], target_sheet_name: Optional[str] = None) -> bytes:
    """
    Takes an openpyxl-generated xlsx bytes/buffer and a dict:
      images_by_cell = {
         'E5': {'id': 'ID_6973526819E6431CB9B92FE7DDB14817', 'bytes': b'...', 'ext': 'jpeg'},
         ...
      }
    Returns complete xlsx bytes with native in-cell images.
    """
    openpyxl_buf.seek(0)
    in_zip = zipfile.ZipFile(openpyxl_buf, 'r')
    out_buf = io.BytesIO()
    out_zip = zipfile.ZipFile(out_buf, 'w', compression=zipfile.ZIP_DEFLATED)
    
    cell_images_xml_parts = []
    cell_images_rels_parts = []
    
    img_counter = 0
    pic_id_counter = 1
    
    # Map cell coordinate (e.g. 'E5') -> image UUID
    cell_to_img_id = {}
    
    for cell_coord, img_info in images_by_cell.items():
        if not img_info or not img_info.get('bytes'):
            continue
            
        img_counter += 1
        pic_id_counter += 1
        img_bytes = img_info['bytes']
        ext = img_info.get('ext', 'jpeg').lower()
        if ext == 'jpg':
            ext = 'jpeg'
            
        img_filename = f"media/image_{img_counter}.{ext}"
        rel_id = f"rIdImg_{img_counter}"
        img_uuid = img_info.get('id') or f"ID_{uuid.uuid4().hex.upper()}"
        cell_to_img_id[cell_coord] = img_uuid
        
        # Write media file
        out_zip.writestr(f"xl/{img_filename}", img_bytes)
        
        # Add to rels
        cell_images_rels_parts.append(
            f'<Relationship Id="{rel_id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="{img_filename}"/>'
        )
        
        # Add to cellimages XML
        cell_images_xml_parts.append(f'''  <etc:cellImage>
    <xdr:pic>
      <xdr:nvPicPr>
        <xdr:cNvPr id="{pic_id_counter}" name="{img_uuid}"/>
        <xdr:cNvPicPr><a:picLocks noChangeAspect="1"/></xdr:cNvPicPr>
      </xdr:nvPicPr>
      <xdr:blipFill>
        <a:blip r:embed="{rel_id}"/>
        <a:stretch><a:fillRect/></a:stretch>
      </xdr:blipFill>
      <xdr:spPr>
        <a:xfrm><a:off x="0" y="0"/><a:ext cx="1000000" cy="1000000"/></a:xfrm>
        <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
      </xdr:spPr>
    </xdr:pic>
  </etc:cellImage>''')

    # If no images, return original bytes
    if not cell_images_xml_parts:
        in_zip.close()
        openpyxl_buf.seek(0)
        return openpyxl_buf.getvalue()

    # Build xl/cellimages.xml
    cellimages_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<etc:cellImages xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
                xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
                xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
                xmlns:etc="http://www.wps.cn/officeDocument/2017/etCustomData">
{''.join(cell_images_xml_parts)}
</etc:cellImages>'''
    out_zip.writestr("xl/cellimages.xml", cellimages_xml.encode('utf-8'))

    # Build xl/_rels/cellimages.xml.rels
    cellimages_rels = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
{''.join(cell_images_rels_parts)}
</Relationships>'''
    out_zip.writestr("xl/_rels/cellimages.xml.rels", cellimages_rels.encode('utf-8'))

    # Find which worksheet xml matches
    sheet_filenames = [n for n in in_zip.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")]
    # Default to first sheet or sheet1
    target_sheet_filename = sheet_filenames[0] if sheet_filenames else "xl/worksheets/sheet1.xml"

    # Process all existing zip members
    for item in in_zip.infolist():
        data = in_zip.read(item.filename)
        
        if item.filename == "[Content_Types].xml":
            content = data.decode('utf-8')
            if 'Extension="jpeg"' not in content:
                content = content.replace('</Types>', '<Default Extension="jpeg" ContentType="image/jpeg"/></Types>')
            if 'Extension="jpg"' not in content:
                content = content.replace('</Types>', '<Default Extension="jpg" ContentType="image/jpeg"/></Types>')
            if 'Extension="png"' not in content:
                content = content.replace('</Types>', '<Default Extension="png" ContentType="image/png"/></Types>')
            if 'PartName="/xl/cellimages.xml"' not in content:
                content = content.replace('</Types>', '<Override PartName="/xl/cellimages.xml" ContentType="application/vnd.wps-officedocument.cellimage+xml"/></Types>')
            data = content.encode('utf-8')

        elif item.filename == "xl/_rels/workbook.xml.rels":
            content = data.decode('utf-8')
            if 'cellimages.xml' not in content:
                content = content.replace('</Relationships>', '<Relationship Id="rIdCellImage_WPS" Type="http://www.wps.cn/officeDocument/2020/cellImage" Target="cellimages.xml"/></Relationships>')
            data = content.encode('utf-8')

        elif item.filename in sheet_filenames:
            content = data.decode('utf-8')
            # Inject formula _xlfn.DISPIMG for each cell
            for cell_coord, img_uuid in cell_to_img_id.items():
                pattern = rf'(<c\s+r="{cell_coord}"[^>]*>)(.*?)(</c>)'
                match = re.search(pattern, content)
                if match:
                    open_tag = match.group(1)
                    if 't="' in open_tag:
                        open_tag = re.sub(r't="[^"]*"', 't="str"', open_tag)
                    else:
                        open_tag = open_tag.rstrip('>') + ' t="str">'
                    
                    formula_val = f'<f>_xlfn.DISPIMG(&quot;{img_uuid}&quot;,1)</f><v>=DISPIMG(&quot;{img_uuid}&quot;,1)</v>'
                    replacement = f'{open_tag}{formula_val}</c>'
                    content = content[:match.start()] + replacement + content[match.end():]
            data = content.encode('utf-8')

        out_zip.writestr(item, data)

    out_zip.close()
    in_zip.close()
    return out_buf.getvalue()
