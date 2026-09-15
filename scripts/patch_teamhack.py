import os, shutil

print("=== Applying Android 2.3 TLS fix to TeamHackLG kernel ===")

# 1. Patch arch/arm/include/asm/tls.h
tls_path = os.path.join('kernel_src', 'arch', 'arm', 'include', 'asm', 'tls.h')
with open(tls_path, 'r', encoding='utf-8') as f:
    tls_content = f.read()

lines = tls_content.splitlines()
new_lines = []
patched = False
for l in lines:
    new_lines.append(l)
    if 'mcr' in l and 'c13, c0, 2' in l and not patched:
        new_lines.append('\tmov\t\\tmp2, #0xffff0fff')
        new_lines.append('\tstr\t\\tp, [\\tmp2, #-15]\t\t@ set TLS value at 0xffff0ff0')
        patched = True

with open(tls_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(new_lines) + '\n')
print("Patched tls.h! Result:", patched)

# 2. Patch arch/arm/kernel/traps.c
traps_path = os.path.join('kernel_src', 'arch', 'arm', 'kernel', 'traps.c')
with open(traps_path, 'r', encoding='utf-8') as f:
    traps_content = f.read()

old_block = 'asm ("mcr p15, 0, %0, c13, c0, 3"\n\t\t\t\t: : "r" (regs->ARM_r0));\n\t\t} else {'
new_block = 'asm ("mcr p15, 0, %0, c13, c0, 3"\n\t\t\t\t: : "r" (regs->ARM_r0));\n\t\t}\n\t\t{'
if old_block in traps_content:
    traps_content = traps_content.replace(old_block, new_block)
    print("Patched traps.c via block replacement!")
else:
    print("Warning: old_block not found directly in traps.c")

with open(traps_path, 'w', encoding='utf-8') as f:
    f.write(traps_content)

# 3. Configure cyanogenmod_m4_defconfig
defconfig_path = os.path.join('kernel_src', 'arch', 'arm', 'configs', 'cyanogenmod_m4_defconfig')
with open(defconfig_path, 'r', encoding='utf-8') as f:
    def_content = f.read()

def_content += '\n# CONFIG_SECURITY is not set\nCONFIG_DEFAULT_SECURITY_DAC=y\nCONFIG_DEFAULT_SECURITY=""\n'
with open(defconfig_path, 'w', encoding='utf-8') as f:
    f.write(def_content)
print("Configured cyanogenmod_m4_defconfig successfully!")

# 4. Copy modern python3-compatible gcc-wrapper.py
gw_src = os.path.join('scripts', 'gcc-wrapper.py')
gw_dst = os.path.join('kernel_src', 'scripts', 'gcc-wrapper.py')
if os.path.exists(gw_src):
    shutil.copy(gw_src, gw_dst)
    print("Copied Python3-compatible gcc-wrapper.py!")

# 5. Fix GNU Make 4.3 compatibility in Makefile
mk_compressed = os.path.join('kernel_src', 'arch', 'arm', 'boot', 'compressed', 'Makefile')
with open(mk_compressed, 'r', encoding='utf-8') as f:
    mk_c = f.read()
mk_c = mk_c.replace(
    '$(obj)/piggy.$(suffix_y).o:  $(obj)/piggy.$(suffix_y) FORCE',
    '$(obj)/piggy.$(suffix_y).o: $(src)/piggy.$(suffix_y).S $(obj)/piggy.$(suffix_y) FORCE\n\t$(call if_changed_dep,as_o_S)'
)
with open(mk_compressed, 'w', encoding='utf-8') as f:
    f.write(mk_c)

mk_usr = os.path.join('kernel_src', 'usr', 'Makefile')
with open(mk_usr, 'r', encoding='utf-8') as f:
    mk_u = f.read()
mk_u = mk_u.replace(
    '$(obj)/initramfs_data.o: $(obj)/initramfs_data.cpio$(suffix_y) FORCE',
    '$(obj)/initramfs_data.o: $(src)/initramfs_data.S $(obj)/initramfs_data.cpio$(suffix_y) FORCE\n\t$(call if_changed_dep,as_o_S)'
)
with open(mk_usr, 'w', encoding='utf-8') as f:
    f.write(mk_u)
print("Applied GNU Make 4.3 build fixes!")

print("=== PATCHING COMPLETE ===")
