/* Deterministic, freestanding microbenchmarks; no libc or prior result files. */
typedef unsigned long u64;
#ifndef KIND
#define KIND 0
#endif
#define N 1600
static long write_out(const char *s, u64 n) {
    long r;
    __asm__ volatile("syscall" : "=a"(r) : "a"(1L), "D"(1L), "S"(s), "d"(n) : "rcx","r11","memory");
    return r;
}
static void checksum(u64 x) {
    char out[] = "checksum=0000000000000000\n";
    for (int i=0;i<16;i++) out[24-i]="0123456789abcdef"[(x>>(i*4))&15];
    write_out(out,26);
}
static u64 links[8192];
int main(void) {
    u64 result=0;
#if KIND == 0
    u64 a=1,b=2,c=3,d=4,e=5,f=6,g=7,h=8;
    for (int i=0;i<N;i++) {
        __asm__ volatile("add $3,%0; add $5,%1; add $7,%2; add $11,%3; add $13,%4; add $17,%5; add $19,%6; add $23,%7"
          : "+r"(a),"+r"(b),"+r"(c),"+r"(d),"+r"(e),"+r"(f),"+r"(g),"+r"(h) :: "cc");
    }
    result=a+b+c+d+e+f+g+h;
#elif KIND == 1
    double a=1,b=2,c=3,d=4,e=5,f=6,g=7,h=8,step=0.25;
    for (int i=0;i<N;i++) {
        __asm__ volatile("addsd %8,%0; addsd %8,%1; addsd %8,%2; addsd %8,%3; addsd %8,%4; addsd %8,%5; addsd %8,%6; addsd %8,%7"
          : "+x"(a),"+x"(b),"+x"(c),"+x"(d),"+x"(e),"+x"(f),"+x"(g),"+x"(h) : "x"(step));
    }
    result=(u64)(a+b+c+d+e+f+g+h);
#elif KIND == 2
    /* Static data initialized here; initialization is included in whole-run timing. */
    for (u64 i=0;i<8192;i++) links[i]=(i+1031)&8191;
    u64 pos=0;
    for (int i=0;i<N;i++) {
        __asm__ volatile("mov (%1,%0,8),%0" : "+r"(pos) : "r"(links) : "memory");
    }
    result=pos;
#elif KIND == 3
    /* Strongly biased branch: 15 of each 16 instances jump to label 1. */
    for (u64 i=0;i<N;i++) {
        __asm__ volatile("test $15,%1; jnz 1f; add $9,%0; jmp 2f; 1: add $1,%0; 2:"
          : "+r"(result) : "r"(i) : "cc");
    }
#elif KIND == 4
    u64 x=0x12345678;
    for (int i=0;i<N;i++) {
        x^=x<<13; x^=x>>7; x^=x<<17;
        __asm__ volatile("test $1,%1; jnz 1f; add $9,%0; jmp 2f; 1: add $1,%0; 2:"
          : "+r"(result) : "r"(x) : "cc");
    }
#elif KIND == 5
    u64 x=1;
    for(int i=0;i<N;i++) {
        __asm__ volatile("imul $3,%0,%0; imul $5,%0,%0; imul $7,%0,%0; imul $11,%0,%0" : "+r"(x));
    }
    result=x;
#endif
    checksum(result);
    return 0;
}
