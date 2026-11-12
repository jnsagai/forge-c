#include <stdint.h>
#include <stddef.h>

uint32_t replace_field(uint32_t original, unsigned lsb, unsigned width, uint32_t replacement)
{
    if (width < 1u || width > 32u) return original;
    if (lsb > 31u)                 return original;
    if (lsb + width > 32u)         return original;

    uint32_t mask;
    if (width == 32u) {
        mask = 0xFFFFFFFFu;
    } else {
        mask = ((uint32_t)((1u << width) - 1u)) << lsb;
    }

    return (original & ~mask) | ((uint32_t)replacement & mask);
}

int poll_match(uint32_t (*read_word)(void *), void *ctx, uint32_t mask,
               uint32_t expected, unsigned max_reads)
{
    if (read_word == NULL) return -1;

    uint32_t target = expected & mask;
    for (unsigned i = 0; i < max_reads; ++i) {
        if ((read_word(ctx) & mask) == target) return 1;
    }
    return 0;
}
