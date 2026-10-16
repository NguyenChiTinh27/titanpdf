import sys
import os
import shutil

# Ensure UTF-8 stdout
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SOURCE_STATIC = os.path.join(PROJECT_ROOT, 'static')
SOURCE_CORE = os.path.join(PROJECT_ROOT, 'core')

TARGET_STATICS = [
    os.path.join(PROJECT_ROOT, r'dist\LUV-PDF\_internal\static'),
    os.path.join(PROJECT_ROOT, r'dist\LUV-PDF\static'),
    r'E:\Tool\_internal\static',
    r'E:\Tool\static'
]

INTERNAL_TARGETS = [
    os.path.join(PROJECT_ROOT, r'dist\LUV-PDF\_internal'),
    r'E:\Tool\_internal'
]

TOOL_ROOT = r'E:\Tool'


def sync_distribution():
    print("=== STARTING FULL DISTRIBUTION SYNC & PORTABLE DEPLOYMENT ===")

    # 1. Sync static assets
    for target in TARGET_STATICS:
        if not os.path.exists(os.path.dirname(target)):
            continue
        print(f"[*] Syncing static to: {target}")
        os.makedirs(target, exist_ok=True)

        for root, dirs, files in os.walk(SOURCE_STATIC):
            rel_dir = os.path.relpath(root, SOURCE_STATIC)
            dst_dir = os.path.join(target, rel_dir) if rel_dir != "." else target
            os.makedirs(dst_dir, exist_ok=True)

            for f in files:
                src_f = os.path.join(root, f)
                dst_f = os.path.join(dst_dir, f)
                shutil.copy2(src_f, dst_f)
        print(f"  [+] Synced static assets successfully to: {target}")

    # 2. Sync backend files (server.py, all core/*.py modules)
    for internal in INTERNAL_TARGETS:
        if not os.path.exists(internal):
            continue
        print(f"[*] Syncing backend modules to: {internal}")

        # Copy server.py
        server_src = os.path.join(PROJECT_ROOT, "server.py")
        server_dst = os.path.join(internal, "server.py")
        if os.path.exists(server_src):
            shutil.copy2(server_src, server_dst)
            print(f"  [+] Copied server.py ({os.path.getsize(server_dst):,} bytes)")

        # Copy entire core directory
        core_dst_dir = os.path.join(internal, "core")
        os.makedirs(core_dst_dir, exist_ok=True)
        for cf in os.listdir(SOURCE_CORE):
            if cf.endswith(".py"):
                c_src = os.path.join(SOURCE_CORE, cf)
                c_dst = os.path.join(core_dst_dir, cf)
                shutil.copy2(c_src, c_dst)
                print(f"  [+] Copied core/{cf} ({os.path.getsize(c_dst):,} bytes)")

    # Sync to E:\Tool root if exists
    if os.path.exists(TOOL_ROOT):
        tool_core = os.path.join(TOOL_ROOT, "core")
        os.makedirs(tool_core, exist_ok=True)
        for cf in os.listdir(SOURCE_CORE):
            if cf.endswith(".py"):
                shutil.copy2(os.path.join(SOURCE_CORE, cf), os.path.join(tool_core, cf))
        server_tool_dst = os.path.join(TOOL_ROOT, "server.py")
        shutil.copy2(os.path.join(PROJECT_ROOT, "server.py"), server_tool_dst)

        # Sync CSLD data/msds_chemical_inventory.db & data/msds_files
        source_db = os.path.join(PROJECT_ROOT, "data", "msds_chemical_inventory.db")
        source_msds_files = os.path.join(PROJECT_ROOT, "data", "msds_files")
        if os.path.exists(source_db):
            for db_target_dir in [
                os.path.join(TOOL_ROOT, "data"),
                os.path.join(PROJECT_ROOT, "dist", "LUV-PDF", "data")
            ]:
                os.makedirs(db_target_dir, exist_ok=True)
                shutil.copy2(source_db, os.path.join(db_target_dir, "msds_chemical_inventory.db"))
                if os.path.exists(source_msds_files):
                    target_msds_files = os.path.join(db_target_dir, "msds_files")
                    os.makedirs(target_msds_files, exist_ok=True)
                    for mf in os.listdir(source_msds_files):
                        src_mf = os.path.join(source_msds_files, mf)
                        if os.path.isfile(src_mf):
                            shutil.copy2(src_mf, os.path.join(target_msds_files, mf))
                print(f"  [+] Synced MSDS database & msds_files to: {db_target_dir}")

    # 3. Deploy LUV-PDF-Portable.exe
    built_portable_exe = os.path.join(PROJECT_ROOT, "dist", "LUV-PDF-Portable.exe")
    if os.path.exists(built_portable_exe) and os.path.exists(TOOL_ROOT):
        target_portable_exe = os.path.join(TOOL_ROOT, "LUV-PDF-Portable.exe")
        print(f"[*] Deploying {built_portable_exe} -> {target_portable_exe}")
        try:
            shutil.copy2(built_portable_exe, target_portable_exe)
            print(f"  [+] Deployed LUV-PDF-Portable.exe successfully! Size: {os.path.getsize(target_portable_exe):,} bytes")
        except Exception as e:
            print(f"  [!] Note when copying portable exe: {e}")

    # 4. Clean up legacy history files and modules in deployment targets
    for hist_cand in [
        os.path.join(TOOL_ROOT, "conversion_history.json"), 
        os.path.join(PROJECT_ROOT, "temp", "conversion_history.json"),
        os.path.join(TOOL_ROOT, "core", "history_manager.py"),
        os.path.join(PROJECT_ROOT, "dist", "LUV-PDF", "_internal", "core", "history_manager.py")
    ]:
        if os.path.exists(hist_cand):
            try:
                os.remove(hist_cand)
                print(f"  [+] Removed legacy history artifact: {hist_cand}")
            except Exception as e:
                print(f"  [!] Note removing history artifact {hist_cand}: {e}")

    print("\n[SUCCESS] All distribution targets and portable executable synchronized successfully!")


if __name__ == '__main__':
    sync_distribution()
