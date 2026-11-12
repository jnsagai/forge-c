#include <stdint.h>
#include <stddef.h>
uint32_t replace_field(uint32_t original, unsigned lsb, unsigned width, uint32_t replacement)
{
 if (width == 0U || width > 32U || lsb > 31U || width > 32U-lsb) return original;
 if (width == 32U) return replacement;
 uint32_t low=(UINT32_C(1)<<width)-UINT32_C(1);
 uint32_t mask=low<<lsb;
 return original ^ ((original ^ (replacement<<lsb)) & mask);
}
int poll_match(uint32_t (*read_word)(void *), void *ctx, uint32_t mask, uint32_t expected, unsigned max_reads)
{
 if (read_word == NULL) return -1;
 while (max_reads != 0U) {
  --max_reads;
  uint32_t word=read_word(ctx);
  if ((word & mask) == (expected & mask)) return 1;
 }
 return 0;
}
