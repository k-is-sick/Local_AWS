import os
import sys
import subprocess

def build():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    main_py = os.path.join(root_dir, "launcher", "main.py")
    dist_dir = os.path.join(root_dir, "dist")
    work_dir = os.path.join(root_dir, "build")

    sep = ";" if sys.platform == "win32" else ":"

    add_data_items = [
        ("docker-compose.yaml", "."),
        ("Dockerfile", "."),
        ("app.py", "."),
        ("requirements.txt", "."),
        ("s3", "s3"),
        ("dynamodb", "dynamodb"),
        ("ec2", "ec2"),
        ("iam", "iam"),
        ("lambda", "lambda"),
        ("templates", "templates"),
        ("static", "static"),
        ("launcher", "launcher"),
        ("shared", "shared")
    ]

    ico_path = os.path.join(root_dir, "launcher", "logo.ico")

    cmd = [
        "pyinstaller",
        main_py,
        "--name=LocalAWS",
        "--onefile",
        "--noconsole",
        "--clean",
        f"--icon={ico_path}",
        f"--distpath={dist_dir}",
        f"--workpath={work_dir}"
    ]

    for src, dst in add_data_items:
        src_path = os.path.join(root_dir, src)
        if os.path.exists(src_path):
            cmd.append(f"--add-data={src_path}{sep}{dst}")

    print("Building LocalAWS.exe with PyInstaller...")
    subprocess.run(cmd, check=True)
    print(f"\nBuild finished successfully! Executable located at: {os.path.join(dist_dir, 'LocalAWS.exe')}")

if __name__ == "__main__":
    build()
