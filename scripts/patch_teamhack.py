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

# 2.5. Patch arch/arm/mm/mmu.c to remove L_PTE_RDONLY from MT_HIGH_VECTORS
# This allows the kernel to write software TLS pointer to 0xffff0ff0 without Data Abort / Panic!
mmu_path = os.path.join('kernel_src', 'arch', 'arm', 'mm', 'mmu.c')
with open(mmu_path, 'r', encoding='utf-8') as f:
    mmu_content = f.read()

old_vec = """\t[MT_HIGH_VECTORS] = {
\t\t.prot_pte  = L_PTE_PRESENT | L_PTE_YOUNG | L_PTE_DIRTY |
\t\t\t\tL_PTE_USER | L_PTE_RDONLY,"""

new_vec = """\t[MT_HIGH_VECTORS] = {
\t\t.prot_pte  = L_PTE_PRESENT | L_PTE_YOUNG | L_PTE_DIRTY |
\t\t\t\tL_PTE_USER,"""

if old_vec in mmu_content:
    mmu_content = mmu_content.replace(old_vec, new_vec)
    print("Patched mmu.c: removed L_PTE_RDONLY from MT_HIGH_VECTORS!")
else:
    print("Warning: old_vec not found in mmu.c!")

with open(mmu_path, 'w', encoding='utf-8') as f:
    f.write(mmu_content)

# 2.6. Patch board-msm7x27a_m4.c for Android 2.3 PMEM GPU devices
board_m4 = os.path.join('kernel_src', 'arch', 'arm', 'mach-msm', 'lge', 'm4', 'board-msm7x27a_m4.c')
if os.path.exists(board_m4):
    with open(board_m4, 'r', encoding='utf-8') as f:
        b_content = f.read()

    pmem_defs = """
#ifdef CONFIG_ANDROID_PMEM
#include <linux/android_pmem.h>

static struct android_pmem_platform_data android_pmem_gpu0_pdata = {
	.name = "pmem_gpu0",
	.size = 16 * 1024 * 1024,
	.memory_type = MEMTYPE_EBI1,
	.allocator_type = PMEM_ALLOCATORTYPE_BITMAP,
	.cached = 0,
};

static struct platform_device android_pmem_gpu0_device = {
	.name = "android_pmem",
	.id = 0,
	.dev = {
		.platform_data = &android_pmem_gpu0_pdata,
	},
};

static struct android_pmem_platform_data android_pmem_gpu1_pdata = {
	.name = "pmem_gpu1",
	.size = 8 * 1024 * 1024,
	.memory_type = MEMTYPE_EBI1,
	.allocator_type = PMEM_ALLOCATORTYPE_BITMAP,
	.cached = 0,
};

static struct platform_device android_pmem_gpu1_device = {
	.name = "android_pmem",
	.id = 1,
	.dev = {
		.platform_data = &android_pmem_gpu1_pdata,
	},
};

static struct android_pmem_platform_data android_pmem_pdata = {
	.name = "pmem",
	.size = 8 * 1024 * 1024,
	.memory_type = MEMTYPE_EBI1,
	.allocator_type = PMEM_ALLOCATORTYPE_BITMAP,
	.cached = 0,
};

static struct platform_device android_pmem_device = {
	.name = "android_pmem",
	.id = 2,
	.dev = {
		.platform_data = &android_pmem_pdata,
	},
};

static struct android_pmem_platform_data android_pmem_adsp_pdata = {
	.name = "pmem_adsp",
	.size = 8 * 1024 * 1024,
	.memory_type = MEMTYPE_EBI1,
	.allocator_type = PMEM_ALLOCATORTYPE_BITMAP,
	.cached = 0,
};

static struct platform_device android_pmem_adsp_device = {
	.name = "android_pmem",
	.id = 3,
	.dev = {
		.platform_data = &android_pmem_adsp_pdata,
	},
};
#endif
"""
    target_common = "static struct platform_device *common_devices[] __initdata = {"
    replacement_common = pmem_defs + "\n" + target_common + """
#ifdef CONFIG_ANDROID_PMEM
	&android_pmem_gpu0_device,
	&android_pmem_gpu1_device,
	&android_pmem_device,
	&android_pmem_adsp_device,
#endif"""
    if target_common in b_content:
        b_content = b_content.replace(target_common, replacement_common)
        print("Patched board-msm7x27a_m4.c: added PMEM devices to common_devices!")

    target_res = "fix_sizes();"
    replacement_res = """fix_sizes();
#ifdef CONFIG_ANDROID_PMEM
	msm7x27a_reserve_table[MEMTYPE_EBI1].size += (16 + 8 + 8 + 8) * 1024 * 1024;
#endif"""
    if target_res in b_content:
        b_content = b_content.replace(target_res, replacement_res)
        print("Patched board-msm7x27a_m4.c: added PMEM memory reservation!")

    with open(board_m4, 'w', encoding='utf-8') as f:
        f.write(b_content)

# 2.7. Copy pmem.c and android_pmem.h and patch drivers/misc/Makefile and drivers/misc/Kconfig
pmem_src = os.path.join('drivers', 'misc', 'pmem.c')
pmem_dst = os.path.join('kernel_src', 'drivers', 'misc', 'pmem.c')
if os.path.exists(pmem_src):
    shutil.copy(pmem_src, pmem_dst)
    print("Copied pmem.c to kernel_src/drivers/misc/pmem.c")
else:
    print("Warning: pmem.c not found at", pmem_src)

pmem_h_src = os.path.join('include', 'linux', 'android_pmem.h')
pmem_h_dst = os.path.join('kernel_src', 'include', 'linux', 'android_pmem.h')
if os.path.exists(pmem_h_src):
    shutil.copy(pmem_h_src, pmem_h_dst)
    print("Copied android_pmem.h to kernel_src/include/linux/android_pmem.h")

misc_mk = os.path.join('kernel_src', 'drivers', 'misc', 'Makefile')
if os.path.exists(misc_mk):
    with open(misc_mk, 'r', encoding='utf-8') as f:
        mk_content = f.read()
    if 'CONFIG_ANDROID_PMEM' not in mk_content:
        mk_content += "\nobj-$(CONFIG_ANDROID_PMEM) += pmem.o\n"
        with open(misc_mk, 'w', encoding='utf-8') as f:
            f.write(mk_content)
        print("Patched kernel_src/drivers/misc/Makefile: added pmem.o!")

misc_kc = os.path.join('kernel_src', 'drivers', 'misc', 'Kconfig')
if os.path.exists(misc_kc):
    with open(misc_kc, 'r', encoding='utf-8') as f:
        kc_content = f.read()
    if 'config ANDROID_PMEM' not in kc_content:
        pmem_kconfig = """
config ANDROID_PMEM
	bool "Android pmem allocator"
	default y

"""
        kc_content = kc_content.replace('menu "Misc devices"', 'menu "Misc devices"\n' + pmem_kconfig)
        with open(misc_kc, 'w', encoding='utf-8') as f:
            f.write(kc_content)
        print("Patched kernel_src/drivers/misc/Kconfig: added ANDROID_PMEM!")


# 3. Use 100% verified working PhilZ recovery kernel config (with TLS fix & no SELinux)
src_cfg = 'e610_working.config'
dst_cfg1 = os.path.join('kernel_src', 'arch', 'arm', 'configs', 'cyanogenmod_m4_defconfig')
dst_cfg2 = os.path.join('kernel_src', '.config')
if os.path.exists(src_cfg):
    shutil.copy(src_cfg, dst_cfg1)
    shutil.copy(src_cfg, dst_cfg2)
    print("Copied e610_working.config directly into kernel config!")
else:
    print("Warning: e610_working.config not found!")

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
