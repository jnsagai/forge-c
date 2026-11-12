# Synthetic reference manual RM9999, timer chapter (feature 020 test fixture, not a real document)

<!-- source: RM9999 p.420 -->
## 43 Basic timer (TMR)

### 43.1 Introduction

The TMR is a synthetic up-counting timer used only by the feature 020 tests.

### 43.3 Functional description

#### 43.3.1 Counter

When enabled, the counter counts up to the period value and then sets the update flag.

#### 43.3.4 One-pulse mode

In one-pulse mode the counter stops at the next update event.

<!-- source: RM9999 p.421 -->
### 43.6 TMR registers

#### 43.6.1 TMR control register (TMR_CR)

Bit 0 CEN: counter enable. Bit 3 OPM: one-pulse mode.

#### 43.6.2 TMR status register (TMR_SR)

Bit 0 UIF: update interrupt flag.
