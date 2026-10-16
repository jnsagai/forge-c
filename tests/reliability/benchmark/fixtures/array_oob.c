#include <stdint.h>
int32_t bench_oob(int32_t x)
{
    int32_t a[4];
    a[4] = x;
    return a[0];
}
