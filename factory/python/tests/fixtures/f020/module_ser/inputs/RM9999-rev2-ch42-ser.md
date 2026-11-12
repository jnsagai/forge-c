# Synthetic reference manual RM9999 (feature 020 test fixture, not a real document)

<!-- source: RM9999 p.410 -->
## 42 Serial interface (SER)

### 42.1 Introduction

The SER is a synthetic full-duplex serial interface used only by the feature 020 tests.

### 42.2 Main features

- Programmable baud rate
- Transmit and receive data registers
- Overrun detection

<!-- source: RM9999 p.411 -->
### 42.3 Functional description

#### 42.3.1 Transmitter

When the interface is enabled, data written to the transmit data register is sent. The transmit-empty flag is set
when the register can accept new data.

#### 42.3.2 Receiver

Received data is available in the receive data register. An overrun is flagged when new data arrives before the
previous data was read.

#### 42.3.5 Loopback mode

In loopback mode the transmitter output is connected internally to the receiver input.

<!-- source: RM9999 p.413 -->
### 42.7 SER registers

#### 42.7.1 SER control register (SER_CR)

Address offset: 0x00. Reset value: 0x0000 0000.

Bit 0 UE: interface enable. Bit 5 LOOP: loopback enable.

#### 42.7.2 SER baud rate register (SER_BRR)

Address offset: 0x04. Reset value: 0x0000 0000.

Bits 15:0 BRR: baud rate divider.

#### 42.7.3 SER interrupt and status register (SER_ISR)

Address offset: 0x08. Reset value: 0x0000 0080.

Bit 7 TXE: transmit data register empty. Bit 3 ORE: overrun error.

#### 42.7.4 SER interrupt flag clear register (SER_ICR)

Address offset: 0x0C. Bit 3 ORECF: overrun error clear flag.

#### 42.7.5 SER transmit data register (SER_TDR)

Address offset: 0x10. Bits 8:0 TDR: transmit data value.

#### 42.7.6 SER receive data register (SER_RDR)

Address offset: 0x14. Bits 8:0 RDR: receive data value.
