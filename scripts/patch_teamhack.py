import os

print("=== Applying Android 2.3 TLS fix to TeamHackLG kernel ===")

# 1. Patch arch/arm/include/asm/tls.h
tls_path = os.path.join('kernel_src', 'arch', 'arm', 'include', 'asm', 'tls.h')
with open(tls_path, 'r', encoding='utf-8') as f:
    tls_content = f.read()

target_tls = """.macro set_tls_v6k, tp, tmp1, tmp2
\tmcr\tp15, 0, \\tp, c13, c0, 3\t\t@ set TLS register
\tmov\t\\tmp1, #0
\tmcr\tp15, 0, \\tmp1, c13, c0, 2\t@ clear user r/w TLS register
\t.endm"""

repl_tls = """.macro set_tls_v6k, tp, tmp1, tmp2
\tmcr\tp15, 0, \\tp, c13, c0, 3\t\t@ set TLS register
\tmov\t\\tmp1, #0
\tmcr\tp15, 0, \\tmp1, c13, c0, 2\t@ clear user r/w TLS register
\tmov\t\\tmp2, #0xffff0fff
\tstr\t\\tp, [\\tmp2, #-15]\t\t@ set TLS value at 0xffff0ff0
\t.endm"""

if target_tls in tls_content:
    tls_content = tls_content.replace(target_tls, repl_tls)
    with open(tls_path, 'w', encoding='utf-8') as f:
        f.write(tls_content)
    print("Successfully patched tls.h!")
else:
    print("Warning: target_tls not found directly, trying line-by-line replace in tls.h...")
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
    print("Patched tls.h via line matching! Result:", patched)

# 2. Patch arch/arm/kernel/traps.c
traps_path = os.path.join('kernel_src', 'arch', 'arm', 'kernel', 'traps.c')
with open(traps_path, 'r', encoding='utf-8') as f:
    traps_content = f.read()

target_traps = """\tcase NR(set_tls):
\t\tthread->tp_value = regs->ARM_r0;
\t\tif (tls_emu)
\t\t\treturn 0;
\t\tif (has_tls_reg) {
\t\t\tasm ("mcr p15, 0, %0, c13, c0, 3"
\t\t\t\t: : "r" (regs->ARM_r0));
\t\t} else {
\t\t\t/*
\t\t\t * User space must never try to access this directly.
\t\t\t * Expect your app to break eventually if you do so.
\t\t\t * The user helper at 0xffff0fe0 must be used instead.
\t\t\t * (see entry-armv.S for details)
\t\t\t */
\t\t\t*((unsigned int *)0xffff0ff0) = regs->ARM_r0;
\t\t}
\t\treturn 0;"""

repl_traps = """\tcase NR(set_tls):
\t\tthread->tp_value = regs->ARM_r0;
\t\tif (tls_emu)
\t\t\treturn 0;
\t\tif (has_tls_reg) {
\t\t\tasm ("mcr p15, 0, %0, c13, c0, 3"
\t\t\t\t: : "r" (regs->ARM_r0));
\t\t}
\t\t*((unsigned int *)0xffff0ff0) = regs->ARM_r0;
\t\treturn 0;"""

if target_traps in traps_content:
    traps_content = traps_content.replace(target_traps, repl_traps)
    with open(traps_path, 'w', encoding='utf-8') as f:
        f.write(traps_content)
    print("Successfully patched traps.c!")
else:
    print("Warning: target_traps not found directly, applying fallback replace in traps.c...")
    # Replace the else block so it's unconditional
    traps_content = traps_content.replace(
        '#ifdef CONFIG_NEEDS_SYSCALL_FOR_CMPXCHG',
        '/* TLS fix for Android 2.3 */\n#ifdef CONFIG_NEEDS_SYSCALL_FOR_CMPXCHG'
    )
    # Simple replace:
    old_block = 'asm ("mcr p15, 0, %0, c13, c0, 3"\n\t\t\t\t: : "r" (regs->ARM_r0));\n\t\t} else {'
    new_block = 'asm ("mcr p15, 0, %0, c13, c0, 3"\n\t\t\t\t: : "r" (regs->ARM_r0));\n\t\t}\n\t\t{'
    traps_content = traps_content.replace(old_block, new_block)
    with open(traps_path, 'w', encoding='utf-8') as f:
        f.write(traps_content)
    print("Patched traps.c via fallback block replacement!")

# 3. Configure cyanogenmod_m4_defconfig
defconfig_path = os.path.join('kernel_src', 'arch', 'arm', 'configs', 'cyanogenmod_m4_defconfig')
with open(defconfig_path, 'r', encoding='utf-8') as f:
    def_content = f.read()

def_content += '\n# CONFIG_SECURITY is not set\nCONFIG_DEFAULT_SECURITY_DAC=y\nCONFIG_DEFAULT_SECURITY=""\n'
with open(defconfig_path, 'w', encoding='utf-8') as f:
    f.write(def_content)
print("Configured cyanogenmod_m4_defconfig successfully!")
print("=== PATCHING COMPLETE ===")
