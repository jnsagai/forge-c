#include <stdint.h>
#include <stddef.h>

uint32_t replace_field(uint32_t original, unsigned lsb, unsigned width, uint32_t replacement)
{
    if (width < 1 || width > 32 || lsb > 31 || lsb + width > 32) {
        return original;
    }

    uint32_t field_mask;
    if (width == 32) {
        field_mask = 0xFFFFFFFFu;
    } else {
        field_mask = ((1u << width) - 1u) << lsb;
    }

    return (original & ~field_mask) | (replacement & field_mask);
}

int poll_match(uint32_t (*read_word)(void *), void *ctx, uint32_t mask,
               uint32_t expected, unsigned max_reads)
{
    if (read_word == NULL) {
        return -1;
    }

    uint32_t exp_masked = expected & mask;
    for (unsigned i = 0; i < max_reads; i++) {
        uint32_t word = read_word(ctx);
        if ((word & mask) == exp_masked) {
            return 1;
        }
    }
    return 0;
}
