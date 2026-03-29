import sys
import argostranslate.package

print("Updating package index...")
argostranslate.package.update_package_index()

available_packages = argostranslate.package.get_available_packages()

print("Searching for fi -> en package...")
package_to_install = None
for p in available_packages:
    if p.from_code == "fi" and p.to_code == "en":
        package_to_install = p
        break

if not package_to_install:
    print("Error: fi -> en package not found in ArgosTranslate repository.")
    sys.exit(1)

print(f"Downloading package {package_to_install}...")
download_path = package_to_install.download()

print("Installing package from path...")
argostranslate.package.install_from_path(download_path)

print("Installed fi -> en package successfully.")
