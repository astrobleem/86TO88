# TEST88 / PCjs 80286 diagnostic (2026-11-02)

## Finding
The original TEST88 full-FLAGS comparison fails solely on architecturally
undefined IMUL status bits, not its observed multiplication result or CF/OF.
No TSR or game changes were made for this diagnosis.

Actual pinned PCjs guest diagnostic inserted INT F7 notification at each
failure entry. That notification skipped the artificial interrupt without
changing guest registers; it only read the test's captured state. Exactly two
failure events occurred:

| Case | Preserved AX | Product BX / expected | Actual FLAGS | Native expected FLAGS | XOR |
|---|---|---|---|---|---|
| 9 imul_a | 01F7 | 0BCA / 0BCA | 0286 | 0246 | 00C0 |
| 10 imul_b | 2000 | C000 / C000 | 0A87 | 0A47 | 00C0 |

00C0 is SF|ZF. CF and OF both clear for case 9 and both set for case 10.
No register, stack or other case failures were recorded. The stock final
T88FAIL printout is misleading for diagnosis because later cases overwrite
its g_ax/g_bx/gotflags/expflags globals before printing lastfail.

PCjs's pinned machines/pcx86/modules/v2/x86func.js fnIMULw changes CF/OF and
leaves the other status bits unchanged on its 80286 core. The TSR uses the same
one-operand IMUL, but intervening slot-address arithmetic leaves different
SF/ZF inputs. Since the TSR merges the captured SF/ZF back into the caller,
those undefined values differ from the test's separate native-IMUL calculation.

## Primary specification
Intel 80286 and 80287 Programmer's Reference Manual (1987), section 3.3.3,
printed page 3-8: IMUL leaves SF, ZF, AF and PF undefined. Its CF and OF are
specified and are retained in the corrected comparison.

https://bitsavers.trailing-edge.com/components/intel/80286/210498-005_80286_and_80287_Programmers_Reference_Manual_1987.pdf

Modern Intel corroboration, IMUL Flags Affected:
https://www.intel.com/content/dam/www/public/us/en/documents/manuals/64-ia-32-architectures-software-developer-vol-2a-manual.pdf

## Bounded recommended source change
Only in src/build_test88.py's flags comparison:

    L.append(" MOV AX, [gotflags]")
    if s["type"] == 4:
        L.append(" XOR AX, [expflags]")
        L.append(" AND AX, 0FF2Bh")
        L.append(" CMP AX, 0")
    else:
        L.append(" CMP AX, [expflags]")

0xFF2B = 0xFFFF & ~(SF|ZF|AF|PF). CF, OF, and unaffected control/reserved bits
remain checked. All register, result, stack, ownership and other case checks
remain unchanged. No bridge change is warranted by this evidence.

The uninstrumented candidate, with only that change, actually produced
T88PASS in the same PCjs 80286 guest.

- candidate-TEST88.COM: 13,696 bytes
- SHA-256: 3231096590db8230cdd8739b383cf1b2b681e0942c2a047fb9268cb0f3810645
- Original TEST88: SHA-256 083c45f9def698672d5febbf9dc4ea90be130abd5de5f46e67cbfa613495d646
- candidate-defined.log: clean pass from uninstrumented candidate
- diagnostic.log: original comparison's exact failing states
- diagnostic-defined.log: instrumented defined-flags comparison pass
- diagnostic.py / diagnostic.mjs: reproducible private diagnostic harness

The diagnosed comparison fix was subsequently integrated into this change set; WM88TSR and the game remain unchanged.

## Separate remaining caveat
The current shift cases also compare AF and multibit OF, which Intel marks
undefined (same original manual, printed page B-97). They pass this PCjs run.
This diagnosis does not establish those comparisons as universally portable,
and no broad rewrite was made without a reproduced failure.
