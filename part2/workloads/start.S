.global _start
.text
_start:
    andq $-16, %rsp
    call main
    movq %rax, %rdi
    movq $60, %rax
    syscall
.section .note.GNU-stack,"",@progbits
