# Synthetic HAL driver guideline (feature 020 test fixture)

## 1 Rules

### 1.1 Handle-based state

Every HAL service takes a handle that holds the instance and its state.

### 1.2 No dynamic memory

A HAL driver does not allocate memory dynamically and does not depend on an operating system.
