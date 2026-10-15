# CMake toolchain file: GNU Arm Embedded, Arm Cortex-M55 (STM32N6), freestanding C11 target build.
# Usage: cmake -S . -B build/target -G Ninja -DCMAKE_TOOLCHAIN_FILE=cmake/arm-none-eabi-cortex-m55.cmake \
#              -DBUILD_TESTING=OFF -DCMAKE_BUILD_TYPE=MinSizeRel
set(CMAKE_SYSTEM_NAME Generic)
set(CMAKE_SYSTEM_PROCESSOR arm)
set(CMAKE_C_COMPILER arm-none-eabi-gcc)
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)  # no hosted link step for compiler checks
set(CMAKE_C_FLAGS_INIT "-mcpu=cortex-m55 -mthumb -mfloat-abi=hard -ffreestanding -ffunction-sections -fdata-sections")
# Reproducible objects: no absolute build paths, deterministic archives.
string(APPEND CMAKE_C_FLAGS_INIT " -ffile-prefix-map=${CMAKE_SOURCE_DIR}=.")
set(CMAKE_C_ARCHIVE_CREATE "<CMAKE_AR> qcD <TARGET> <LINK_FLAGS> <OBJECTS>")
set(CMAKE_C_ARCHIVE_FINISH "<CMAKE_RANLIB> -D <TARGET>")
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
