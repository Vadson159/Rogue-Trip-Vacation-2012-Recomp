/* Unified multi-region native game dispatcher for Rogue Trip: Vacation 2012.
 *
 * Links both statically recompiled executables into one PC binary:
 *   - SLUS_006.43 (NTSC-U 60 Hz — FullRUS, Rus, and stock USA)  [rt_us_*]
 *   - SLES_014.17 (PAL 50 Hz — Europe)                          [rt_eu_*]
 *
 * Selected automatically at boot from the mounted disc's SYSTEM.CNF / PS-X EXE
 * header via psx_game_select_boot_exe().
 */

#include <ctype.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "psx_runtime.h"

/* Namespaced SLUS_006.43 (US / FullRUS / Rus) backend */
extern int rt_us_psx_game_address_in_text(uint32_t addr);
extern int rt_us_psx_game_text_native_ok(uint32_t addr);
extern int rt_us_psx_game_text_native_ok_full(uint32_t addr);
extern int rt_us_psx_dispatch_game_compiled(CPUState* cpu, uint32_t addr);
extern int rt_us_psx_game_is_function_entry(uint32_t addr);

/* Namespaced SLES_014.17 (Europe PAL) backend */
extern int rt_eu_psx_game_address_in_text(uint32_t addr);
extern int rt_eu_psx_game_text_native_ok(uint32_t addr);
extern int rt_eu_psx_game_text_native_ok_full(uint32_t addr);
extern int rt_eu_psx_dispatch_game_compiled(CPUState* cpu, uint32_t addr);
extern int rt_eu_psx_game_is_function_entry(uint32_t addr);

enum {
    RT_VARIANT_US = 0, /* SLUS_006.43: entry 0x801549B0 (FullRUS / Rus / USA) */
    RT_VARIANT_EU = 1  /* SLES_014.17: entry 0x801547B4 (Europe PAL)          */
};

static int g_rt_active_variant = RT_VARIANT_US;

static int contains_icase(const char* hay, const char* needle) {
    size_t nlen;
    if (!hay || !needle) return 0;
    nlen = strlen(needle);
    if (nlen == 0) return 0;
    for (; *hay; ++hay) {
        size_t i = 0;
        while (i < nlen && hay[i] &&
               toupper((unsigned char)hay[i]) == toupper((unsigned char)needle[i])) {
            ++i;
        }
        if (i == nlen) return 1;
    }
    return 0;
}

void psx_game_select_boot_exe(const char* boot_name, uint32_t entry_pc) {
    if (entry_pc == 0x801547B4u || contains_icase(boot_name, "SLES_014.17") ||
        contains_icase(boot_name, "SLES-01417")) {
        g_rt_active_variant = RT_VARIANT_EU;
        fprintf(stdout,
                "roguetrip: selected native backend SLES_014.17 (Europe PAL, entry=0x%08X)\n",
                entry_pc);
    } else {
        g_rt_active_variant = RT_VARIANT_US;
        fprintf(stdout,
                "roguetrip: selected native backend SLUS_006.43 (US / FullRUS / Rus NTSC, entry=0x%08X)\n",
                entry_pc);
    }
}

int psx_game_address_in_text(uint32_t addr) {
    return (g_rt_active_variant == RT_VARIANT_EU)
               ? rt_eu_psx_game_address_in_text(addr)
               : rt_us_psx_game_address_in_text(addr);
}

int psx_game_text_native_ok(uint32_t addr) {
    return (g_rt_active_variant == RT_VARIANT_EU)
               ? rt_eu_psx_game_text_native_ok(addr)
               : rt_us_psx_game_text_native_ok(addr);
}

int psx_game_text_native_ok_full(uint32_t addr) {
    return (g_rt_active_variant == RT_VARIANT_EU)
               ? rt_eu_psx_game_text_native_ok_full(addr)
               : rt_us_psx_game_text_native_ok_full(addr);
}

int psx_dispatch_game_compiled(CPUState* cpu, uint32_t addr) {
    return (g_rt_active_variant == RT_VARIANT_EU)
               ? rt_eu_psx_dispatch_game_compiled(cpu, addr)
               : rt_us_psx_dispatch_game_compiled(cpu, addr);
}

int psx_game_is_function_entry(uint32_t addr) {
    return (g_rt_active_variant == RT_VARIANT_EU)
               ? rt_eu_psx_game_is_function_entry(addr)
               : rt_us_psx_game_is_function_entry(addr);
}
