#include <stdint.h>
#include <stddef.h>

uint32_t replace_field(uint32_t original, unsigned lsb, unsigned width, uint32_t replacement)
{
    if (width < 1 || width > 32 || lsb > 31 || lsb + width > 32)
        return original;

    uint32_t mask;
    if (width == 32)
        mask = 0xFFFFFFFFu;
    else
        mask = ((1u << width) - 1u) << lsb;

    uint32_t value = (replacement & ((1u << width) - 1u)) << lsb;

    return (original & ~mask) | value;
}

int poll_match(uint32_t (*read_word)(void *), void *ctx, uint32_t mask,
               uint32_t expected, unsigned max_reads)
{
    if (read_word == 0)
        return -1;

    for (unsigned i = 0; i < max_reads; i++) {
        if ((read_word(ctx) & mask) == (expected & mask))
            return 1;
    }

    return 0;
}
