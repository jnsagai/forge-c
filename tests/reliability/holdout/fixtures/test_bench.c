#include <stdio.h>
int bench_value(void);
int main(void) { if (bench_value() == 41) { printf("UT-901 PASS\n"); return 0; } printf("UT-901 FAIL\n"); return 1; }
