unsigned char crc8(const unsigned char *data, unsigned long n) {
    unsigned char crc = 0;
    for (unsigned long i = 0; i < n; i++) {
        crc ^= data[i];
        for (int j = 0; j < 8; j++) {
            if (crc & 0x80)
                crc = (crc << 1) ^ 0x07;
            else
                crc <<= 1;
        }
    }
    return crc;
}
int main(void){const unsigned char d[]="123456789";return crc8(d,9)!=0xf4 || crc8(d,0)!=0;}
