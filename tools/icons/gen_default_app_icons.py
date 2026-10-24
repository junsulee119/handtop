"""Pixel-art icons for the default (Debian) apps, under the apps' own icon names, so the packages'
files and .desktop entries stay untouched:

  dark set   hicolor/scalable/apps/<name>.png          (/usr/local/share/icons is searched before
                                                       /usr/share for the same subdirectory)
  light set  Handtop-Light/scalable/apps/<name>.png    (the light icon theme, see gen_wifi_icons.py;
                                                       rg35xxh-theme makes it the GTK icon theme)

56x56 (27-grid art x2 + 1 px margin, the drawer's size). For the drawer's 56 px GTK picks the
scalable directory; the PNG is used at its own size there.

  foot         Terminal: the Enable SSH terminal without text and key, with a big ">_" prompt
  org.xfce.thunar  Files (Thunar): a blue folder with a sheet of paper, one set for both themes
  org.xfce.mousepad  Text Editor (Mousepad): a yellow legal pad, one set for both themes
  chromium           Web Browser (Chromium): a wireframe globe with a mouse pointer, one set for both themes
  htop               System Monitor (htop): the Terminal frame with a green heartbeat line
  micro              Code Editor (micro): the Terminal frame with syntax-coloured code lines
  qpdfview           PDF Viewer (qpdfview): a page with a red "PDF" band; light version outlined
  xarchiver          Archive Manager (Xarchiver): the File Manager folder with a zipper

Window title bars: labwc looks the icon up at exactly 22 px, where the package's own 22x22 file
would win over our scalable one, so a 22x22 copy (smoothly scaled down from the 56 px icon, dark set
only: labwc reads hicolor) goes to hicolor/22x22/apps/<name>.png too.

Usage: python3 gen_default_app_icons.py <icons folder>    (e.g. overlay/usr/local/share/icons)
"""
import os
import sys

from PIL import Image

from gen_app_icons import archive_icon, browser_icon, code_icon, files_icon, monitor_icon, notepad_icon, pdf_icon, terminal_icon

ICONS = {"foot": terminal_icon, "org.xfce.thunar": files_icon,
         "org.xfce.mousepad": notepad_icon, "chromium": browser_icon,
         "htop": monitor_icon, "micro": code_icon,
         "qpdfview": pdf_icon, "xarchiver": archive_icon}


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    for folder, light in (("hicolor", False), ("Handtop-Light", True)):
        os.makedirs(f"{root}/{folder}/scalable/apps", exist_ok=True)
        for name, fn in ICONS.items():
            fn(light).save(f"{root}/{folder}/scalable/apps/{name}.png")
    os.makedirs(f"{root}/hicolor/22x22/apps", exist_ok=True)
    for name, fn in ICONS.items():                      # labwc title bar size
        fn(False).resize((22, 22), Image.LANCZOS).save(f"{root}/hicolor/22x22/apps/{name}.png")
