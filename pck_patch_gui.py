#!/usr/bin/env python3
"""
pck_patch_gui.py – GUI tool to create and apply patches for Godot .pck files.
Provides:
  - Create Patch: compare two .pck/.exe files and extract only new/changed files.
  - Apply Patch: merge a patch folder into an original .pck/.exe and repack (optionally build a .vpk).
"""

import os
import sys
import tempfile
import shutil
import struct
import hashlib
import zipfile
import tkinter as tk
from tkinter import filedialog, messagebox

GDPC_MAGIC = b'GDPC'
PCK_EXE_FILETYPES = [
    ("PCK / EXE files", "*.pck *.exe"),
    ("PCK files", "*.pck"),
    ("EXE files", "*.exe"),
]

# -------------------------------------------------------------------
# EXE / embedded PCK helpers
# -------------------------------------------------------------------
def find_embedded_pck_offset(exe_path):
    """
    Locate an embedded Godot PCK inside an .exe.
    Returns the absolute byte offset of the GDPC magic, or None.
    """
    with open(exe_path, 'rb') as f:
        f.seek(0, 2)
        file_size = f.tell()

        # Method 1: standard Godot footer (last 8 bytes)
        if file_size >= 12:
            f.seek(-8, 2)
            footer = f.read(8)
            if footer[4:] == GDPC_MAGIC:
                pck_offset = struct.unpack('<i', footer[:4])[0]
                if 0 <= pck_offset < file_size:
                    f.seek(pck_offset)
                    if f.read(4) == GDPC_MAGIC:
                        return pck_offset

        # Method 2: brute-force magic scan (fallback)
        chunk = 1 << 20  # 1 MB
        pos = 0
        while pos < file_size:
            f.seek(pos)
            data = f.read(chunk + 4)
            idx = data.find(GDPC_MAGIC)
            if idx != -1:
                return pos + idx
            pos += chunk

    return None

# -------------------------------------------------------------------
# Utility functions for PCK handling
# -------------------------------------------------------------------
def read_header_index(src_path):
    """Read header + file index from a Godot 3 .pck or embedded .exe."""
    index = {}
    with open(src_path, 'rb') as f:
        magic = f.read(4)

        if magic == GDPC_MAGIC:
            # Standalone PCK
            pass
        else:
            # Try EXE with embedded PCK
            pck_off = find_embedded_pck_offset(src_path)
            if pck_off is None:
                raise ValueError(f"Not a Godot PCK and no embedded PCK found in: {src_path!r}")
            f.seek(pck_off + 4)  # skip magic

        version = struct.unpack('<4I', f.read(16))
        reserved = f.read(64)
        file_count = struct.unpack('<i', f.read(4))[0]
        
        for _ in range(file_count):
            path_len = struct.unpack('<i', f.read(4))[0]
            raw = f.read(path_len)
            path = raw.decode('utf-8').rstrip('\x00')
            offset, size = struct.unpack('<q q', f.read(16))
            f.read(16)  # skip stored MD5
            index[path] = (offset, size)
            
    return version, reserved, index

def extract_pck(src_path, out_dir):
    """Extract every file from a .pck or .exe into out_dir."""
    os.makedirs(out_dir, exist_ok=True)
    _, _, index = read_header_index(src_path)
    with open(src_path, 'rb') as f:
        for virt_path, (offset, size) in index.items():
            rel = virt_path.replace('res://', '')
            dest = os.path.join(out_dir, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            f.seek(offset)
            data = f.read(size)
            with open(dest, 'wb') as out:
                out.write(data)

def repack_pck(extracted_dir, new_pck_path, src_pck=None):
    """Repack files under extracted_dir into a new .pck, copying header from src_pck if given."""
    if src_pck:
        version, reserved, _ = read_header_index(src_pck)
    else:
        version, reserved = (0,0,0,0), b'\x00'*64

    # collect items
    items = []
    for root, _, files in os.walk(extracted_dir):
        for fn in sorted(files):
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, extracted_dir).replace(os.sep, '/')
            virt = f"res://{rel}"
            size = os.path.getsize(full)
            md5  = hashlib.md5(open(full, 'rb').read()).digest()
            items.append((virt, full, size, md5))

    # compute header & offsets
    header_size = 4 + 16 + 64 + 4
    idx_entries_size = sum(
        4 + len(virt.encode('utf-8')) + 8 + 8 + 16
        for virt, _, _, _ in items
    )
    base_offset = header_size + idx_entries_size

    offsets, cur = [], base_offset
    for _, _, size, _ in items:
        offsets.append(cur)
        cur += size

    # write .pck
    with open(new_pck_path, 'wb') as out:
        out.write(b'GDPC')
        out.write(struct.pack('<4I', *version))
        out.write(reserved)
        out.write(struct.pack('<i', len(items)))
        for (virt, _, size, md5), off in zip(items, offsets):
            vb = virt.encode('utf-8')
            out.write(struct.pack('<i', len(vb)))
            out.write(vb)
            out.write(struct.pack('<q', off))
            out.write(struct.pack('<q', size))
            out.write(md5)
        for _, full, _, _ in items:
            with open(full, 'rb') as f:
                out.write(f.read())

def build_vpk(patched_pck_path, template_dir, content_dir, output_vpk):
    """Assemble a full VPK: copy template → content_dir, inject patched .pck, zip to output_vpk."""
    if not os.path.isdir(template_dir):
        raise FileNotFoundError(f"VPK template '{template_dir}' not found")
    # clean content_dir
    if os.path.isdir(content_dir):
        shutil.rmtree(content_dir)
    shutil.copytree(template_dir, content_dir)
    # replace game_data/game.pck
    gd = os.path.join(content_dir, 'game_data')
    if os.path.isdir(gd):
        shutil.rmtree(gd)
    os.makedirs(gd, exist_ok=True)
    shutil.copy2(patched_pck_path, os.path.join(gd, 'game.pck'))
    # zip up with 0777 perms
    with zipfile.ZipFile(output_vpk, 'w', compression=zipfile.ZIP_STORED) as zf:
        for root, dirs, files in os.walk(content_dir):
            for d in dirs:
                full = os.path.join(root, d)
                rel  = os.path.relpath(full, content_dir).replace(os.sep, '/')
                if not rel.endswith('/'):
                    rel += '/'
                zi = zipfile.ZipInfo(rel)
                zi.external_attr = (0o777 << 16) | 0x10
                zf.writestr(zi, b'')
            for f in files:
                full = os.path.join(root, f)
                rel  = os.path.relpath(full, content_dir).replace(os.sep, '/')
                zi = zipfile.ZipInfo(rel)
                zi.external_attr = (0o777 << 16)
                data = open(full, 'rb').read()
                zf.writestr(zi, data)

# -------------------------------------------------------------------
# Patch creation utilities
# -------------------------------------------------------------------
def hash_file(path):
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            h.update(chunk)
    return h.hexdigest()

def collect_files(root_dir):
    """Walk root_dir and return dict of relative_path -> full_path."""
    files = {}
    for dirpath, _, filenames in os.walk(root_dir):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root_dir).replace("\\", "/")
            files[rel] = full
    return files

def create_patch(src_orig, src_patched, output_folder):
    """Extract two sources (.pck or .exe), compare, and copy new/changed to output_folder."""
    tmp1 = tempfile.mkdtemp(prefix="pck_orig_")
    tmp2 = tempfile.mkdtemp(prefix="pck_patched_")
    try:
        extract_pck(src_orig, tmp1)
        extract_pck(src_patched, tmp2)
        files1 = collect_files(tmp1)
        files2 = collect_files(tmp2)

        # prepare output
        if os.path.exists(output_folder):
            shutil.rmtree(output_folder)
        for rel, full2 in files2.items():
            full1 = files1.get(rel)
            if not full1 or hash_file(full1) != hash_file(full2):
                dst = os.path.join(output_folder, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(full2, dst)
    finally:
        shutil.rmtree(tmp1)
        shutil.rmtree(tmp2)

# -------------------------------------------------------------------
# GUI Application
# -------------------------------------------------------------------
class PatchGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PCK Patch Tool")
        self.geometry("600x420")
        
        # --- Create Patch Frame ---
        frm1 = tk.LabelFrame(self, text="Create Patch", padx=10, pady=10)
        frm1.pack(fill="x", padx=10, pady=5)

        # Original .pck / .exe
        tk.Label(frm1, text="Original (.pck/.exe):").grid(row=0, column=0, sticky="e")
        self.orig_pck_var = tk.StringVar()
        tk.Entry(frm1, textvariable=self.orig_pck_var, width=50).grid(row=0, column=1)
        tk.Button(frm1, text="Browse...", command=self.browse_orig_pck).grid(row=0, column=2)

        # Patched .pck / .exe
        tk.Label(frm1, text="Patched (.pck/.exe):").grid(row=1, column=0, sticky="e")
        self.patched_pck_var = tk.StringVar()
        tk.Entry(frm1, textvariable=self.patched_pck_var, width=50).grid(row=1, column=1)
        tk.Button(frm1, text="Browse...", command=self.browse_patched_pck).grid(row=1, column=2)

        # Output patch folder
        tk.Label(frm1, text="Patch Folder:").grid(row=2, column=0, sticky="e")
        self.patch_folder_var = tk.StringVar()
        tk.Entry(frm1, textvariable=self.patch_folder_var, width=50).grid(row=2, column=1)
        tk.Button(frm1, text="Browse...", command=self.browse_patch_folder).grid(row=2, column=2)

        tk.Button(frm1, text="Create Patch", bg="#4CAF50", fg="white",
                  command=self.on_create_patch).grid(row=3, column=1, pady=10)

        # --- Apply Patch Frame ---
        frm2 = tk.LabelFrame(self, text="Apply Patch", padx=10, pady=10)
        frm2.pack(fill="x", padx=10, pady=5)

        # Original .pck / .exe for apply
        tk.Label(frm2, text="Original (.pck/.exe):").grid(row=0, column=0, sticky="e")
        self.apply_orig_var = tk.StringVar()
        tk.Entry(frm2, textvariable=self.apply_orig_var, width=50).grid(row=0, column=1)
        tk.Button(frm2, text="Browse...", command=self.browse_apply_orig).grid(row=0, column=2)

        # Patch folder to apply
        tk.Label(frm2, text="Patch Folder:").grid(row=1, column=0, sticky="e")
        self.apply_patch_var = tk.StringVar()
        tk.Entry(frm2, textvariable=self.apply_patch_var, width=50).grid(row=1, column=1)
        tk.Button(frm2, text="Browse...", command=self.browse_apply_patch).grid(row=1, column=2)

        # Output .pck
        tk.Label(frm2, text="Output .pck:").grid(row=2, column=0, sticky="e")
        self.output_pck_var = tk.StringVar(value="game_merged.pck")
        tk.Entry(frm2, textvariable=self.output_pck_var, width=50).grid(row=2, column=1)
        tk.Button(frm2, text="Save As...", command=self.save_output_pck).grid(row=2, column=2)

        # Build VPK option
        self.build_vpk_var = tk.BooleanVar()
        cb = tk.Checkbutton(frm2, text="Build VPK after repack", variable=self.build_vpk_var,
                            command=self.toggle_vpk_options)
        cb.grid(row=3, column=1, sticky="w")

        # VPK template folder
        tk.Label(frm2, text="VPK Template:").grid(row=4, column=0, sticky="e")
        self.vpk_template_var = tk.StringVar()
        self.vpk_template_entry = tk.Entry(frm2, textvariable=self.vpk_template_var, width=50, state="disabled")
        self.vpk_template_entry.grid(row=4, column=1)
        self.vpk_template_btn = tk.Button(frm2, text="Browse...", command=self.browse_vpk_template, state="disabled")
        self.vpk_template_btn.grid(row=4, column=2)

        # Output VPK
        tk.Label(frm2, text="Output .vpk:").grid(row=5, column=0, sticky="e")
        self.output_vpk_var = tk.StringVar(value="game.vpk")
        self.output_vpk_entry = tk.Entry(frm2, textvariable=self.output_vpk_var, width=50, state="disabled")
        self.output_vpk_entry.grid(row=5, column=1)
        self.output_vpk_btn = tk.Button(frm2, text="Save As...", command=self.save_output_vpk, state="disabled")
        self.output_vpk_btn.grid(row=5, column=2)

        tk.Button(frm2, text="Apply Patch", bg="#2196F3", fg="white",
                  command=self.on_apply_patch).grid(row=6, column=1, pady=10)

    # --- Browse callbacks ---
    def browse_orig_pck(self):
        path = filedialog.askopenfilename(title="Select original .pck or .exe", filetypes=PCK_EXE_FILETYPES)
        if path: self.orig_pck_var.set(path)

    def browse_patched_pck(self):
        path = filedialog.askopenfilename(title="Select patched .pck or .exe", filetypes=PCK_EXE_FILETYPES)
        if path: self.patched_pck_var.set(path)

    def browse_patch_folder(self):
        path = filedialog.askdirectory(title="Select output patch folder")
        if path: self.patch_folder_var.set(path)

    def browse_apply_orig(self):
        path = filedialog.askopenfilename(title="Select original .pck or .exe", filetypes=PCK_EXE_FILETYPES)
        if path: self.apply_orig_var.set(path)

    def browse_apply_patch(self):
        path = filedialog.askdirectory(title="Select patch folder")
        if path: self.apply_patch_var.set(path)

    def save_output_pck(self):
        path = filedialog.asksaveasfilename(title="Save merged .pck as", defaultextension=".pck",
                                            filetypes=[("PCK files","*.pck")])
        if path: self.output_pck_var.set(path)

    def browse_vpk_template(self):
        path = filedialog.askdirectory(title="Select VPK template folder")
        if path: self.vpk_template_var.set(path)

    def save_output_vpk(self):
        path = filedialog.asksaveasfilename(title="Save .vpk as", defaultextension=".vpk",
                                            filetypes=[("VPK files","*.vpk")])
        if path: self.output_vpk_var.set(path)

    def toggle_vpk_options(self):
        state = "normal" if self.build_vpk_var.get() else "disabled"
        for widget in (self.vpk_template_entry, self.vpk_template_btn,
                       self.output_vpk_entry, self.output_vpk_btn):
            widget.config(state=state)

    # --- Action handlers ---
    def on_create_patch(self):
        orig = self.orig_pck_var.get()
        patched = self.patched_pck_var.get()
        out = self.patch_folder_var.get()
        if not (os.path.isfile(orig) and os.path.isfile(patched)):
            messagebox.showerror("Error", "Please select two valid .pck or .exe files.")
            return
        if not out:
            messagebox.showerror("Error", "Please select an output patch folder.")
            return
        try:
            create_patch(orig, patched, out)
            messagebox.showinfo("Success", f"Patch created in:\n{out}")
        except Exception as e:
            messagebox.showerror("Error creating patch", str(e))

    def on_apply_patch(self):
        orig = self.apply_orig_var.get()
        patch = self.apply_patch_var.get()
        out_pck = self.output_pck_var.get()
        if not (os.path.isfile(orig) and os.path.isdir(patch)):
            messagebox.showerror("Error", "Please select a valid original file and patch folder.")
            return
        try:
            # extract and merge
            tmp = tempfile.mkdtemp()
            extract_pck(orig, tmp)
            
            # merge patch
            for root, _, files in os.walk(patch):
                for fn in files:
                    src = os.path.join(root, fn)
                    rel = os.path.relpath(src, patch)
                    dst = os.path.join(tmp, rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
                    
            # repack
            repack_pck(tmp, out_pck, src_pck=orig)
            
            # optionally build VPK
            if self.build_vpk_var.get():
                tpl = self.vpk_template_var.get()
                out_vpk = self.output_vpk_var.get()
                content_tmp = tempfile.mkdtemp()
                build_vpk(out_pck, tpl, content_tmp, out_vpk)
                shutil.rmtree(content_tmp)
                messagebox.showinfo("Done", f"Repacked .pck → {out_pck}\nBuilt .vpk → {out_vpk}")
            else:
                messagebox.showinfo("Done", f"Repacked .pck → {out_pck}")
        except Exception as e:
            messagebox.showerror("Error applying patch", str(e))
        finally:
            if 'tmp' in locals() and os.path.isdir(tmp):
                shutil.rmtree(tmp)

if __name__ == "__main__":
    app = PatchGUI()
    app.mainloop()