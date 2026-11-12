unsigned int popcount32(unsigned int x) {
    unsigned int count = 0;
    for (int i = 0; i < 32; i++) {
        count += (x >> i) & 1U;
    }
    return count;
}
int main(void){return popcount32(0)!=0 || popcount32(0xffffffffu)!=32 || popcount32(0x80000001u)!=2;}
