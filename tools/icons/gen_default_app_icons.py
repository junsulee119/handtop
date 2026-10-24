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

Usage: python3 gen_default_app_icons.py <icons folder>    (e.g. overlay/usr/local/share/icons)
"""
import os
import sys

from gen_app_icons import files_icon, terminal_icon

ICONS = {"foot": terminal_icon, "org.xfce.thunar": files_icon}


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    for folder, light in (("hicolor", False), ("Handtop-Light", True)):
        os.makedirs(f"{root}/{folder}/scalable/apps", exist_ok=True)
        for name, fn in ICONS.items():
            fn(light).save(f"{root}/{folder}/scalable/apps/{name}.png")
