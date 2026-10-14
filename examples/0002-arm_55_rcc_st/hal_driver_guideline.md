Driver EmbSW Cube2 HAL drivers
SAD
Software Architecture and Design
Document information
Project: EmbSW Cube2
Author: B. JABRI
Version 1.2
MEDOC Id: cx911487
(document template: cx560194 version: 2.2
Approval Table
Project Role Name
Cube2 EmbSW Architect Lead M.MASTOURI
Document history
Date Author Version Description
21- February -2025 B.JABRI 1.2_P1 First Proposed version for Cube2.
Second Proposed version for Cube2. With
24-September-2025 B.JABRI 1.2_P2 comments fixes + HAL security
architecture added
02-October-2025 B.JABRI 1.2_P3 Reworked version, submitted for approval
02-October-2025 B.JABRI 1.2 Approved version
1

Contents
1. About this document ....................................................................................... 8
1.1. Purpose ............................................................................................................... 8
1.2. Scope .................................................................................................................. 8
1.3. Terms and acronyms definitions ........................................................................ 8
1.3.1. Definitions ................................................................................... 8
1.3.2. Acronyms .................................................................................... 9
2. References ....................................................................................................... 11
3. General HAL & LL design aspects .............................................................. 12
3.1. Architecture principles for resources management .......................................... 12
4. HAL & LL drivers’ overview ....................................................................... 13
5. HAL & LL layered drivers ........................................................................... 15
5.1. HAL Inter-series APIs Compatibility Rules .................................................... 15
5.1.1. Configuration Structures Compatibility: ................................... 15
5.1.2. HAL_PPP_SetFeature APIs Compatibility: .............................. 16
5.1.3. HAL System APIs: .................................................................... 16
5.1.4. Processing APIs: ........................................................................ 16
6. HAL & LL drivers’ folder structure ............................................................ 17
7. HAL & LL drivers’ files ................................................................................ 19
7.1. stm32_hal header file ....................................................................................... 21
7.2. stm32tnxx_hal module ..................................................................................... 22
7.3. stm32tnxx_hal_def.h module ........................................................................... 23
7.4. HAL PPP module files ..................................................................................... 25
7.5. HAL Core files ................................................................................................. 26
7.6. HAL utilities ..................................................................................................... 27
7.7. LL driver files ................................................................................................... 27
7.8. HAL OS port modules ...................................................................................... 28
7.9. HAL Time Base modules ................................................................................. 29
7.10. HAL specific coding rules and convention .................................................... 33
7.11. HAL naming rules .......................................................................................... 34
8. HAL/LL standalone templates...................................................................... 39
8.1. Common templates ........................................................................................... 40
8.1.1. HAL configuration file .............................................................. 40
2

8.1.2. stm32_ll.h header file ................................................................ 42
8.1.3. stm32_assert.h header file ......................................................... 43
8.2. Other templates impacting the HAL and LL behaviour: stm32_external_env.h
header file ................................................................................................................ 44
8.3. HAL timebase templates .................................................................................. 45
8.3.1. mx_timx.c/.h .............................................................................. 45
8.3.1. mx_rtc.c/.h ................................................................................. 48
8.3.1. stm32_hal_timebase.h ............................................................... 48
8.4. HAL OS templates ........................................................................................... 50
8.4.1. stm32_hal_os.c/.h ...................................................................... 50
9. HAL/LL inclusion model ............................................................................... 51
10. HAL Data structures and types .................................................................. 53
10.1. HAL Peripherals instances ............................................................................. 53
10.2. HAL Peripherals handles................................................................................ 54
10.3. HAL configuration structures ......................................................................... 57
10.4. HAL parameter types ..................................................................................... 58
10.5. HAL callback types ........................................................................................ 59
11. HAL drivers’ APIs ....................................................................................... 60
11.1. Initialization and deinitialization APIs ........................................................... 67
11.1.1. HAL PPP initialization ............................................................ 67
11.1.2. HAL PPP deinitialization ........................................................ 68
11.1.3. HAL PPP instance retrieving ................................................... 70
11.2. Configuration APIs ........................................................................................ 71
11.2.1. HAL PPP global configuration ................................................ 71
11.2.1. HAL PPP configuration reset .................................................. 74
11.2.2. HAL PPP sub-block configuration .......................................... 75
11.2.3. HAL PPP unitary configuration .............................................. 78
11.2.1. Linking HAL DMA driver to HAL PPP driver ....................... 79
11.2.1. Setting and Getting user data ................................................... 80
11.3. HAL process and I/O operation APIs ............................................................ 81
11.3.1. Polling/blocking model ........................................................... 83
11.3.2. Interrupt asynchronous model ................................................. 86
11.3.3. DMA asynchronous model ...................................................... 89
11.3.4. Aborting an asynchronous process .......................................... 92
3

11.3.5. Asynchronous model, filtering optional interrupts .................. 92
11.3.6. Monitoring model .................................................................... 97
11.4. HAL IRQ Handler and callback ................................................................... 101
11.4.1. HAL IRQ Handler ................................................................. 101
11.4.2. HAL callbacks ....................................................................... 103
11.5. Optional Features control APIs .................................................................... 108
11.5.1. Features that take effect immediately: ................................... 109
11.5.1. Features that can be enabled or disabled: .............................. 109
11.5.1. Features that require configuration and Enable/Disable split 110
11.6. HAL Programming model ............................................................................ 111
11.6.1. User parameters validity check ............................................. 111
11.6.2. State machine ......................................................................... 111
11.6.3. Error management ................................................................. 126
11.6.4. status and return ..................................................................... 131
11.6.5. HAL buses Acquire/Release mechanism .............................. 136
11.7. HAL RCC Clock management ..................................................................... 138
11.7.1. Oscillators enabling and control services .............................. 139
11.7.2. PLL configuration and control services ................................ 139
11.7.3. System Clock Source Selection APIs .................................... 140
11.7.4. Busses Prescalers Configuration APIs .................................. 141
11.7.5. Peripheral Clock management APIs ...................................... 142
11.7.6. Peripheral Clock source management APIs .......................... 143
11.7.7. Reset System Clock Configuration ....................................... 145
11.7.8. RCC reset ............................................................................... 145
11.7.9. Additional HAL RCC Services ............................................. 146
11.8. HAL Time base management ....................................................................... 146
11.8.1. Changing the time base tick period and priority ................... 147
11.8.2. HAL tick increment ............................................................... 148
11.8.3. HAL delays ............................................................................ 148
11.8.4. HAL get tick .......................................................................... 149
11.8.5. HAL get tick priority and frequency ..................................... 149
11.8.6. HAL tick suspends and resume ............................................. 149
11.8.7. HAL timeout .......................................................................... 150
11.8.8. Tick-less timeout ................................................................... 152
4

11.9. HAL OS Abstraction Layer .......................................................................... 153
11.10. HAL over LL layering model ..................................................................... 158
12. LL drivers ................................................................................................... 160
12.1. Overview ...................................................................................................... 160
12.2. Low Layer files ............................................................................................ 161
12.3. APIs definition levels ................................................................................... 162
12.3.1. low level ................................................................................ 163
12.3.2. Middle level ........................................................................... 163
12.3.3. High level .............................................................................. 163
12.4. APIs Categories ............................................................................................ 164
12.5. Functions coding rules ................................................................................. 164
12.6. Functions prototypes .................................................................................... 166
12.7. Functions arguments .................................................................................... 166
12.8. Functions implementation ............................................................................ 168
12.8.1. Local variables ....................................................................... 168
12.8.2. Operations on registers .......................................................... 168
12.8.3. Boolean operations ................................................................ 169
12.9. Naming rules ................................................................................................ 169
12.9.1. Naming convention ............................................................... 169
12.9.1. General naming rules ............................................................. 170
12.9.2. Functions naming rules .......................................................... 171
12.9.3. Macros naming rules ............................................................. 173
12.9.4. Literal’s naming rules ............................................................ 173
12.9.5. Functions definition rules ...................................................... 174
12.10. Usage scenarios .......................................................................................... 177
12.10.1. User application based on LL only ...................................... 178
12.10.2. User application with mixed HAL and LL .......................... 179
12.11. Cohabitation with HAL .............................................................................. 179
12.11.1. Initializing a peripheral using the Low layer ....................... 179
12.11.2. Control functions using the Low layer ................................ 180
12.11.1. Using HAL operation APIs with the Low layer .................. 181
12.12. Internal integration in HAL drivers ............................................................ 182
13. HAL/LL drivers: security support ........................................................... 188
13.2. RIF and GTZC HAL and LL drivers ........................................................... 188
5

13.2.1. RIF and GTZ HAL driver’s architecture ............................... 189
13.2.2. HAL and LL RIF-aware/TZ-aware peripherals APIs ........... 210
13.2.3. Security compile-time conditional checks ............................. 224
13.2.4. Privilege compile-time conditional checks ........................... 226
14. HAL Versioning and dependencies files .................................................. 228
6

1. About this document
1.1. Purpose
This Document is part of the STM32Cube Cube2 Firmware SAD v1.2, which is split into
several official documents. This document focuses on the HAL and LL layers.
This document covers the following topics:
• The overall HAL & LL drivers architecture principles.
1.2. Scope
This document applies in the frame of the STM32 Cube2 firmware project and is intended for
all software developers and testers assigned to this project.
1.3. Terms and acronyms definitions
1.3.1. Definitions
Term Definition
Label A label is a single text associated to a resource, it can be used
lonely or with other text(s) to build a full alias
Alias An alias a full name representing a naming alternative for a
resource
Firmware Set of c/h files offering common services for a specific
component
functionality, example: USB Library, JPEG codec…etc.
Firmware layer Set of firmware components, which provides simplified access, and
interface methods to a common functionality.
CMSIS-PACK Describe a delivery mechanism for software components, device
parameters, and evaluation board support.
8

Term Definition
Code gen template Common files in handlebar format used with the parameters
JSON one for code generation
Example project Example sources with IDE and configuration files for a given
board
Example project CMSIS-PACK containing Example sources with IDE and
pack
configuration files for all supported ST boards with PDSC file,
a pack can be zipped or unzipped.
Example sources Applicative sources for one example with configuration files and
templates.
PDSC file XML-formatted file to describe a CMSIS-PACK in term of
content, dependencies to core, toolchains, or other components.
Platform Set of common services provided for a given STM32 series
associated with a software framework or components and
hardware boards and materials.
PPP/ppp Generic term to represent an STM32 peripheral example I2C
Protocol Set of rules and regulations that determine how data is
transmitted between the firmware components or the data traffic
model in a peripheral.
stm32tnxx Generic term to represent an STM32 series where "tn" represents
the series name, eg stm32u5xx.
User template Common file in .c or .h files provided by a component to be
copied in the in the user space and filled by the user.
1.3.2. Acronyms
Acronym Definition
AES Advanced Encryption Standard
API Application Programming Interface
BSP Board Support Package
CMSIS Cortex Microcontroller Software Interface Standard
CPU Central Processing Unit
DFP Device Family Pack
IDE Integrated Development Environment
LL Low Layer drivers
MSP MCU Specific Package
MW Middleware
PDSC Pack DeSCription
PPP STM32 peripheral or block
RTOS Real Time Operating System
SDMMC Secure Digital Multimedia Card
TZ Trust Zone (security)
9

Acronym Definition
USB Universal Serial Bus
10

2. References

| ID  | Title  | Versio | Doc ID / Link  |
| --- | ------ | ------ | -------------- |
n
| [1]  | EmbSW Cube2 Firmware Top SAD  | 1.2  | cx745929  |
| ---- | ----------------------------- | ---- | --------- |
| [2]  | EmbSW Cube2 Firmware          | 1.2  | cx873278  |
Configuration and code generation
| [3]  | Cube2 functional scope       | 2.3d      | functional scope  |
| ---- | ---------------------------- | --------- | ----------------- |
| [4]  | Open-CMSIS-Pack-spec online  |    1.7.2  | LINK              |
documentation
| [5]  | Ecosystem_Cube2_HW_and_SW_instances  | 1.0  | cx778679  |
| ---- | ------------------------------------ | ---- | --------- |
study
| [6]   | OpenCMSIS Project Format Definition  | N.A.  | Github    |
| ----- | ------------------------------------ | ----- | --------- |
| [7]   | EmbSW Cube2 CMP                      | 1.4   | cx742905  |
| [8]   | EmbSW packaging rules guidelines     | 4.3   | cx582636  |
| [9]   | EmbSW C coding Standard              | 5.6   | cx561795  |
| [10]  | EmbSW Secure Coding Rules            | 1.1   | cx694430  |
[11]   EmbSW Cube2 security architecture support  1.2_P2  cx927152

11

3. General HAL & LL design aspects
The Portable APIs layer (HAL and Low-Layer drivers) provides a generic, multi-instance and
simple set of APIs to interact with the upper layer (application, libraries and stacks). It is
composed of an APIs set that is directly built around a generic architecture and allows the
build-upon layers, like the middleware layer, to implement its functions without knowing in-
depth the used STM32 device. This improves the library code reusability and guarantees an
easy portability on other devices and STM32 families.
The HAL drivers have to offer a rich set of APIs to interact easily with the application upper
layers. Each driver consists of a set of functions covering the full peripheral features. The
development of each driver is driven by a common APIs, which standardizes the driver
structure, the functions and the parameter names.
3.1. Architecture principles for resources management
The following principles should be considered within the HAL/LL drivers:
• The resource types and defines must belong to the given SW layer: The resource types
and defines must be prefixed by the layer prefix : ex “HAL_” or “hal_” then the module
(Ex HAL_FLASH or hal_flash)
• Each SW layer must use its own resources and types: data structures, enum, error
management …
• Layering resources translation: In case of vertical layering (Ex HAL on top of the LL),
a translation phase is required inside the upper layer implementation to accommodate to
the lower layer resources (user must not care about it)
• In case of cohabitating 2 layers at user application (Horizontal interaction): a translation
API must be provided allowing the user to move from a Layer A type to the equivalent
Layer B type regarding the required objects.
12

4. HAL & LL drivers’ overview
The HAL (Hardware Abstraction Layer) drivers consist of a set of driver modules, each
associated to a standalone peripheral. In some cases, a module is dedicated to a peripheral's
functional mode. For example, several modules exist for the USART peripheral: the UART
driver module, the USART driver module, and the SMARTCARD driver module.
• HAL Main Features
o Cross-Family Portable APIs: These cover common peripheral features as well as
family or device-specific peripheral features.
o API Programming Models: Most HAL drivers implement three API
programming models: polling, interrupt, and DMA.
o RTOS Compliant APIs: Fully reentrant APIs with appropriate check and return
“BUSY” at function entry in case of the requested operation is not possible.
APIs. Systematic usage of timeouts in polling mode.
o Peripheral Multi-Instance Support: This allows concurrent API calls for multiple
instances of a given peripheral (e.g., USART1, USART2).
o User-Callback Functions: Most HAL drivers rely on user-callback functions for
asynchronous programming models: Peripheral interrupt events and Error
events.
o Peripheral System-Level Initialization/De-Initialization: This includes clock,
GPIOs, interrupt, and DMA, which must be done at the application level using
the appropriate HAL system driver (e.g., HAL RCC, HAL GPIO, HAL Cortex,
HAL DMA). These initialization sequences must be performed before
configuring the given HAL driver. Note that STM32CubeMX2 offers code
generation capabilities for these initialization sequences, and peripheral clock
enabling can be performed intrinsically during initialization if the feature is
enabled in the configuration file.
o Bus Services: AcquireBus and ReleaseBus services (for bus-type drivers like
I2C, SPI, etc.) ensure safe hardware access to prevent concurrent access to
driver processes and handle objects.
o Timeouts for Blocking Processes: Timeouts can be simple counters or time-
based.
For a given HAL peripheral driver, all APIs must be implemented within a single
stm32tnxx_hal_ppp.c file. The corresponding stm32tnxx_hal_ppp.h header file provides an
interface to the application layer with the available APIs. The HAL APIs are classified into
three categories:
o Common Functions: These are generic APIs common to all STM32 series. They
provide a user-friendly and functional aspect-oriented interface to the application,
13

similar to generic functions available in most public solutions with standardized
APIs. The common APIs allow upper firmware components to call these services
with light configuration affecting only the peripheral instances, while the low-level
interfaces' implementation in high-level firmware components remains consistent.
o STM32 Series-Specific Functions: These APIs apply only to all device part
numbers within a given STM32 series.
o Device-Specific Functions: These APIs are defined by specific features relative to a
given part number and are delimited by different conditional defines (peripheral
version, feature support, peripheral availability, etc.) .
Unlike Low-Layer drivers (see HAL Low-Layer section), HAL drivers are functionality-
oriented rather than IP/HW oriented.
14

5. HAL & LL layered drivers
The HAL (Hardware Abstraction Layer) drivers are built on top of the Low Layer (LL) drivers
when available and applicable for the given peripherals. For example, the HAL TIM driver is
built on top of the LL TIM driver. However, due to the complexity of certain peripherals and
protocols, such as FDCAN, there are no corresponding Low Layer drivers. In these cases, only
a HAL driver is provided, such as the HAL FDCAN driver.
5.1. HAL Inter-series APIs Compatibility Rules
The compatibility of HAL APIs is crucial to ensure the portability of the HAL across different
STM32 series. API compatibility applies to all "C" elements in the stm32tnxx_hal_ppp.h
header files, including defines, enumerations, structures, and functions.
5.1.1. Configuration Structures Compatibility:
By configuration structures, we mean global configuration structures, sub-block or sub-
instance configuration structures, and feature configuration structures. The following rules
apply:
• API Break Authorization: API breaks are only allowed for configurations that are called
only during the peripheral initialization phase . This does not apply to APIs that can be
called dynamically by the user to change the PPP behaviour at runtime.
• Structure Content: It is permissible to have different configuration structure content
when the hardware differs. However, if a given structure field addresses the same
configuration scope, the field naming must remain the same. The structure naming must
also remain the same if applicable to the given series or be completely removed if not
applicable.
• Field Names: From one product to another, we must:
15

o Keep the same configuration structure names (when the structure is applicable
to the given series).
o Maintain the same field names when these fields correspond to features
available in the given series.
o Remove the corresponding field when the feature is not available in the given
series.
o Add new fields when new features are available in the given series.
• Field Values: The possible values for fields (enumerations or defines) must have the
same naming when applicable to the given series or be removed when not applicable. It
is also possible to add additional possible values when new for the given series.
• SetItem/GetItem APIs: These APIs must follow the corresponding configuration
elements (naming and possible values).
5.1.2. HAL_PPP_SetFeature APIs Compatibility:
• Naming: If it concerns the same feature scope, the API naming must remain the same.
• Parameters: It is permissible to have different parameter numbers if some are not
applicable to the given series. For parameters that are still applicable, the parameter
naming must remain the same. The same rule about the parameter's possible values as
the configuration structure applies here.
5.1.3. HAL System APIs:
• Different APIs: All the system/SoC-related IPs can have different APIs if the features
are different (e.g., Cortex, PWR, SYSCFG, RCC).
• Same Features: If the feature or a parameter is the same, keep the same naming.
Parameters' number and list can change if the given series SoC features are different. If
the features are the same, the API naming must remain the same.
Example:
HAL_RCC_LSI_Enable(void); //on Series X
HAL_RCC_LSI_Enable(uint32_t divider); // on Series Y
In the above, both APIs have the same scope (enabling the LSI), but on series X, there is no
divider, so no parameter is needed. On series Y, the LSI requires a divider, so a parameter is
included.
5.1.4. Processing APIs:
The processing APIs and control APIs (APIs that can be called dynamically by the
application) must not change. No API break is allowed in this case.
16

6. HAL & LL drivers’ folder structure
The HAL folder is organized as follow:
▪ .config subfolder must contain the configuration artefacts including the HAL drivers
configuration parameters and templates, and any other configuration helpers
▪ deprecated subfolder must contain the required files to describe the deprecated APIs and
ensure transition to the new APIs. The deprecated files must be used when a compatibility
break occurs between two HAL2 versions. It is not intended to ensure backward
compatibility with Cube 1.x HAL.
▪ hal subfolder must provide the stm32 HAL drivers. This folder must provide the HAL
source and header files stm32tnxx_hal_ppp.c/.h . The HAL core drivers (Ex
stm32tnxx_usb_core.c/.h, stm32tnxx_fmc_core.c/.h …) must be also placed in this folder.
▪ ll subfolder must provide the stm32 LL drivers. This folder must provide the LL header
files stm32tnxx_ll_ppp.h. Note that the LL source files stm32tnxx_ll_ppp.c have been
removed.
▪ os_port subfolder must provide a HAL OS abstraction layer. Services within this OSAL
are limited to semaphore and mutex usage, it is intended to be used by the HAL but it can
be also used by any other layer that needs to abstract these services. The os_port must
support FreeRTOS, and a “no os” variant.
▪ templates subfolder must contain the template source files that need to be copied and
customized into the user application when using the HAL in standalone (w/o code
generation). As an example, the HAL conf header file must be copied and customized into
the user application.
▪ timebases subfolder must provide the HAL time base implementation with 3 possible
flavors: based on TIMER, based on RTC alarm, and based on RTC wakeup. These are
ready to use components that are not configurable. Nevertheless, these components require
17

the corresponding peripheral TIMER or RTC to be initialized and configured either
through the configuration or by the user when in standalone mode (without code
generation). In the case of a standalone application (w/o code generation) and depending
on the peripheral used as HAL time base (RTC or TIMER), the user needs to copy and
customize the corresponding mx_timx.c/.h or mx_rtc.c/.h TIM/RTC file from the template
subfolder.
▪ utils subfolder must provide the HAL utilities modules: example
utils/i2c_timing/stm32_utils_i2c.c/.h allowing to calculate the I2C timing values need
by the HAL_I2C_Init.
▪ doc subfolder must contain the dependencies .md file which contain the dependencies
table of the different HAL components.
▪ The release notes, readme, license and also the pdsc files that list the given series HAL
pack content and components are provided directly under the top driver folder.
18

7. HAL & LL drivers’ files
The HAL & LL drivers are composed of the following set of files:
File Description
hal
stm32_hal.h HAL global include file: to be series agnostic, this file is the
central file to be included by the application for the HAL.
stm32tnxx_hal.c This file provides the following APIs: The HAL
initialization deinitialization, The HAL Tick management
and APIs allowing to retrieve the device unique ID and the
HAL drivers version.
stm32tnxx_hal.h stm32tnxx_hal.c header file.
stm32tnxx_hal_ppp.c PPP peripheral/module driver file.
It provides the implementation of APIs that are common to
all STM32 devices, also specific functionalities linked to
the series (no more stm32tnxx_hal_ppp_ex.c/h).
Example: stm32tnxx_hal_adc.c, stm32tnxx_hal_i2c.c …etc.
stm32tnxx_hal_ppp.h Header file of the PPP peripheral/module driver C file
It includes common data, handle, enumeration structures,
define statements and macros, as well as the exported
generic and specific functions.
Example: stm32tnxx_hal_adc.h, stm32tnxx_hal_i2c.h,
…etc.
stm32tnxx_ppp_core.c Peripheral core driver that can be accessed from one or
more HAL drivers. It offers a set of APIs and services used
by the upper HAL PPP driver.
Example: stm32tnxx_fmc_core.c offers a set of API used
by stm32tnxx_hal_sdram.c, stm32tnxx_hal_sram.c,
stm32tnxx_hal_nor.c, stm32tnxx_hal_nand.c, …
stm32tnxx_ppp_core.h Header file of the core driver C file. It is included in the
HAL PPP driver header file, thus making the core driver as
intrinsic add-on of the HAL PPP driver that is not visible
from the application. Example: stm32tnxx_fmc_core.h,
stm32tnx_usb_core.h…
19

stm32tnxx_hal_def.h Common HAL resources such as common define
statements, enumerations, structures, macros and HAL
include files.
ll
stm32tnxx_ll_ppp.h Low layer drivers for peripherals covered by the low layer
drivers’ program
os_port
stm32tnxx_hal_os.c HAL OS abstraction layer implementation file.
It provides the implementation of the HAL OSAL services.
2 flavour must be provided: one based on FreeRTOS and a
bare metal one based the Cortex services
stm32tnxx_hal_os.h Header file of the HAL OSAL providing the required APIs.
It is included in the stm32_hal.h under the compilation flag
USE_HAL_MUTEX
timebases
stm32_hal_timebase_rtc_alarm.c Provides the implementation of the HAL timebase using
RTC alarm
stm32_hal_timebase_rtc_wakeup.c Provides the implementation of the HAL timebase using
RTC wakeup
stm32_hal_timebase_tim.c Provides the implementation of the HAL timebase using a
TIMER
templates
stm32tnxx_hal_conf.h HAL configuration file (Header file)
Designed to customize the behaviour of the HAL modules.
Provided as a ready to use template with all HAL modules
enabled and with Default module features defines applied.
It is to be used by standalone users only (not using
STM32CubeMX2). In case of using STM32CubeMX2 with
code generation, this file is generated according to the user
choices.
stm32_assert.h HAL assert header file: provide assert macros for HAL
parameters and HAL state checks
stm32_ll.h Provided as a ready to use template. The file provides a
single, series-agnostic inclusion point for the required LL
driver header files of a given STM32 series.
It is to be used by standalone users only (not using
STM32CubeMX2). By default, it contains inclusion of all
the LL driver header files of a given STM32 series. It can
be used as is or can be copied to the user space and
customized according to the required LL drivers by the
application.
In case of using STM32CubeMX2 with code generation,
this file is generated according to the user choices.
stm32tnxx_hal_os.h/.c Provide an empty implementation of the HAL OS
abstraction. These files serve as a skeleton of the required
HAL OS APIs that must be implemented by users who need
to customize the HAL OSAL (Operating System
Abstraction Layer) implementation.
20

mx_tim.h/.c Template files containing the HAL TIM "X" or RTC
mx_rtc.h/.c timebase configuration function. These templates are to be
used when the application needs to use the TIM "X" or an
RTC as a time base for HAL (instead of the SysTick).
When STM32CubeMX2 code generation is not used.
In case of using STM32CubeMX2 with code generation,
this file is generated according to the user choices.
stm32_hal_timebase.h A template file to be used when customizing the HAL “time
base” to use a TIMER or the RTC as a HAL time base. It is
designed to include the required file the mx_timx.h or
mx_rtc.h.
It contains also redirection aliases to the TIMER “init” and
“get handle” functions.
It is to be used by standalone users only (not using
STM32CubeMX2). In case of using STM32CubeMX2 with
code generation, this file is generated according to the user
choices.
utils
stm32_utils_ppp.h/.c Header and implementation files of the required PPP utils
modules, offering additional helper functions to support the HAL
and LL drivers.
7.1. stm32_hal header file
The stm32_hal.h is the entry point header file for any application using the HAL. The
stm32_hal.h file must include (respecting the following order)fv
▪ The stm32tnxx_hal.h
▪ The stm32_hal_os.h under the conditional flag USE_HAL_MUTEX
▪ The different HAL PPP modules stm32tnxx_hal_ppp.h under the conditional flag
USE_HAL_PPP_MODULE
o Note: the HAL system modules must be included first (RCC, GPIO, PWR,
GTZC, DMA)
▪ The stm32_assert.h under the conditional flag USE_ASSERT_DBG_PARAM or
USE_ASSERT_DBG_STATE
Note: the stm32_assert.h file is provided as a template to copied into the application and
customized by the user if needed.
#ifndef STM32_HAL_H
#define STM32_HAL_H
#ifdef __cplusplus
extern "C" {
#endif
#include "stm32tnxx_hal.h"
#if defined(USE_HAL_MUTEX) && (USE_HAL_MUTEX == 1)
#include "stm32_hal_os.h"
#endif /* USE_HAL_MUTEX == 1 */
#if defined(USE_HAL_RCC_MODULE) && (USE_HAL_RCC_MODULE == 1)
#include "stm32u5xx_hal_rcc.h"
#endif /* USE_HAL_RCC_MODULE==1U */
#if defined(USE_HAL_GPIO_MODULE) && (USE_HAL_GPIO_MODULE == 1)
#include "stm32u5xx_hal_gpio.h"
#endif /* USE_HAL_GPIO_MODULE==1U */
21

#if defined(USE_HAL_DMA_MODULE) && (USE_HAL_DMA_MODULE == 1)
#include "stm32u5xx_hal_dma.h"
#endif /* USE_HAL_DMA_MODULE==1U */
...
#if defined(USE_HAL_PPP_MODULE) && (USE_HAL_PPP_MODULE == 1)
#include "stm32u5xx_hal_ppp.h"
#endif /* USE_HAL_PPP_MODULE==1U */
...
#if defined(USE_FULL_ASSERT)
#ifndef USE_ASSERT_DBG_PARAM
#define USE_ASSERT_DBG_PARAM
#endif /* !USE_ASSERT_DBG_PARAM */
#ifndef USE_ASSERT_DBG_STATE
#define USE_ASSERT_DBG_STATE
#endif /* !USE_ASSERT_DBG_STATE */
#endif /* USE_FULL_ASSERT */
#if defined(USE_ASSERT_DBG_PARAM) || defined(USE_ASSERT_DBG_STATE)
#include "stm32_assert.h"
#else
#define ASSERT_DBG_PARAM(expr) ((void) 0U)
#define ASSERT_DBG_STATE(state,val) ((void)0U)
#endif /* USE_ASSERT_DBG_PARAM || USE_ASSERT_DBG_STATE */
#ifdef __cplusplus
}
#endif
#endif /* STM32_HAL_H */
7.2. stm32tnxx_hal module
The stm32tnxx_hal module must be limited to the following services:
▪ HAL Init and De-Init
▪ Tick/Time base management
▪ An API to retrieve the device unique ID
▪ An API to retrieve the HAL version
The stm32tnxx_hal module APIs and services must be consistent across all STM32 series and
limited to the aforementioned services. The implementation of these APIs might vary from
one series to another. Nevertheless, the API list and prototypes must remain the same across
all series.
Contrary to HAL1, the specific SoC services APIs (e.g., DBGCMU, SYCFG, SBS, etc.) must
not be provided within the stm32tnxx_hal module. Instead, they must be offered by the
following modules:
▪ The APIs that are related to the DBGMCU must be provided by the HAL module:
stm32tnxx_hal_dbgmcu.h/.c
▪ The APIs that are related to the SBS must be provided by the HAL module:
stm32tnxx_hal_sbs.h/.c
▪ APIs related to the SYSCFG must be provided by the HAL module:
stm32tnxx_hal_syscfg.h/.c
▪ APIs related to the VREFBUF must be provided by the HAL module:
stm32tnxx_hal_vrefbuf.h/.c (note that the API must be HAL_VREFBUF_XXX
(without SYSCFG)
▪ ART/PREFETCH APIs must be available within the HAL flash module
▪ EXTI APIs (if any) must be provided by the HAL_EXTI driver
22

The stm32tnxx_hal module must provide the common set of APIs for all STM32 series:
hal_status_t HAL_Init(void);
hal_status_t HAL_DeInit(void);
hal_status_t HAL_InitTick(hal_tickFreq_t tick_freq, uint32_t tick_priority)
void HAL_Delay(uint32_t Delay);
uint32_t HAL_GetTick(void);
uint32_t HAL_GetTickPrio(void);
hal_tickFreq_t HAL_GetTickFreq(void);
void HAL_SuspendTick(void);
void HAL_ResumeTick(void);
uint32_t HAL_GetVersion(void);
hal_status_t HAL_GetDeviceUniqueID(hal_device_uid_t *uid);
7.3. stm32tnxx_hal_def.h module
The stm32tnxx_hal_def.h must provide essential configurations and definitions for the STM32
HAL. It includes the following:
• HAL Configuration Definitions:
o By including the stm32tnxx_hal_conf.h, it provides the necessary configuration
settings for the HAL.
• Essential Types and Definitions Related to STM32TN Devices:
o By including the specific Device Family Pack (DFP) header file, such
as stm32u5xx.h, it ensures the inclusion of essential types and definitions
related to the given STM32TN devices.
o Additionally, it includes other essential types by incorporating the standard
headers stddef.h.
• HAL Status Enumeration and Defines:
o The hal_status_t enumeration type, used by the HAL APIs to return status, is
defined within this file.
o It also defines the HAL maximum delay (HAL_MAX_DELAY).
o The file includes defines for the HAL Peripheral Clock enabling model, which
are used to activate or deactivate the Peripheral Clock within
various HAL_PPP_Init functions according to the user choices set in
the stm32tnxx_hal_conf.h.
• HAL_CHECK_UPDATE_STATE Macro:
o The macro HAL_CHECK_UPDATE_STATE allows checking and updating
the state with two flavours according to
the USE_HAL_CHECK_PROCESS_STATE option set in
the stm32tnxx_hal_conf.h.
o An implementation with atomic check and update of the state from one
original state to one destination state
if USE_HAL_CHECK_PROCESS_STATE is defined to 1.
23

o An implementation with direct assignment of the state to the new
desired state without any check
if USE_HAL_CHECK_PROCESS_STATE is defined to 0.
/** @file stm32tnxx_hal_def.h */
/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef STM32TNXX_HAL_DEF_H
#define STM32TNXX_HAL_DEF_H
#ifdef __cplusplus
extern "C" {
#endif
/* Includes ------------------------------------------------------------------*/
#include "stm32tnxx_hal_conf.h"
#include "stm32tnxx.h"
#include <stddef.h>
#include <math.h>
/* Exported types ------------------------------------------------------------*/
/**
* @brief HAL Status structures definition
*/
typedef enum
{
HAL_OK = 0x00000000U, /* HAL operation completed successfully */
HAL_ERROR = 0xFFFFFFFFU, /* HAL operation completed with error */
HAL_BUSY = 0x55555555U, /* HAL concurrent process ongoing */
HAL_INVALID_PARAM = 0xAAAAAAAAU, /* HAL invalid parameter */
HAL_TIMEOUT = 0x5A5A5A5AU /* HAL operation exceeds user timeout */
} hal_status_t;
/* Exported defines ------------------------------------------------------------*/
#define HAL_MAX_DELAY 0xFFFFFFFFU
#define HAL_TICK_INT_LOWEST_PRIORITY ((1UL << __NVIC_PRIO_BITS) - 1UL)
/**
* @brief HAL PPP clock model activation definition
* @details These defines are used inside each HAL_PPP_Init function to indicate
* the clock model to be used.
* This model is declared inside stm32u5xx_hal_conf.h like this:
* #define USE_HAL_PPP_CLK_ENABLE_MODEL HAL_CLK_ENABLE_XXXX */
#define HAL_CLK_ENABLE_NO 0U /*<! No clock activation in PPP */
#define HAL_CLK_ENABLE_PERIPH_ONLY 1U /*<! PERIPH Clock activation only */
#define HAL_CLK_ENABLE_PERIPH_PWR_SYSTEM 2U /*<! PERIPH Clock activation including PWR and/or system */
...
By providing these configurations and definitions, the stm32tnxx_hal_def.h ensures that the
HAL is properly configured and ready to be used with the given STM32TN devices.
24

7.4. HAL PPP module files
HAL (Hardware Abstraction Layer) drivers must provide a high-level, user-friendly interface
for interacting with the microcontroller's peripherals. They must abstract the complexity of
direct register manipulation, making it easier to develop applications without needing in-depth
knowledge of the hardware. The HAL drivers are designed to be portable and scalable,
supporting a wide range of STM32 series and peripherals.
The HAL (Hardware Abstraction Layer) must be designed to offer several key benefits:
• Ease of Use: The HAL must abstract the complexity of direct register manipulation,
significantly simplifying the interaction with peripherals for developers. This
abstraction layer must allow developers to focus on higher-level application logic
without delving into low-level hardware details.
• Portability: The HAL must be designed for portability, enabling its use across
different STM32 series microcontrollers. This must facilitate code reuse and
scalability, allowing the development of versatile applications that can be easily
adapted to various hardware platforms.
• Comprehensive Functionality: The HAL must provide a wide range of
functionalities, including initialization, configuration, control, and state management of
peripherals. This comprehensive support must ensure that all necessary operations for
peripheral management are readily available, enhancing development efficiency.
• Reliable Support: The HAL must be well-documented and backed by
STMicroelectronics. This extensive documentation and support must ensure reliability
and ease of integration, reducing development time and improving overall software
quality.
File Naming Convention:
• Header File: stm32tnxx_hal_ppp.h
• Source File: stm32tnxx_hal_ppp.c
This module contains the implementation of the HAL functions for the PPP peripheral specific
to the STM32TN series. It is composed of a header file and a source file that cover all the
functional features supported by the given peripheral for the specified functional scope.
These files together provide a standardized interface for interacting with the PPP peripheral on
the STM32 TNXX series, ensuring consistency and ease of use across different projects and
applications.
For example:
25

▪ HAL CRC Module: The HAL CRC module of the STM32U5 series is composed of a
source file (stm32u5xx_hal_crc.c) and a header file (stm32u5xx_hal_crc.h). It abstracts
all the features of the CRC peripheral.
▪ HAL UART Module: The HAL UART module is composed of a source file
(stm32u5xx_hal_uart.c) and a header file (stm32u5xx_hal_uart.h). It abstracts all the
UART functionalities (Universal Asynchronous Receiver/Transmitter) of the USART
and LPUART peripherals.
The stm32tnxx_hal_ppp.h is the HAL PPP module header file. It contains:
▪ Data Structures: Definitions of data structures used to configure and manage the PPP
peripheral.
▪ Enumerations: Enumerations for various configuration options and statuses for the PPP
peripheral.
▪ Defines: for various constants and configuration parameters related to the PPP
peripheral.
▪ Function Prototypes: Declarations of all the public functions implemented in the
corresponding .c file.
The stm32tnxx_hal_ppp.c contains the implementation of the HAL (Hardware Abstraction
Layer) functions for the PPP (Peripheral Placeholder) module specific to the STM32 TNXX
series. It includes the following:
▪ Initialization and De-initialization Functions: Functions to initialize and de-initialize
the HAL PPP handle associated to a given instance of the PPP peripheral.
▪ Configuration Functions: Functions to configure the PPP peripheral parameters.
▪ Control Functions: Functions to control the operation of the PPP peripheral, such as
starting, stopping, and managing interrupts.
▪ Status Functions: Functions to check the status and handle errors for the PPP
peripheral.
▪ Callback Functions: Functions to handle callback events triggered by the PPP
peripheral.
7.5. HAL Core files
Peripheral core drivers are designed to be accessed by one or more HAL drivers. They offer a
set of APIs and services used by the upper HAL driver(s). From the user's perspective, core
drivers are not directly accessible; they are utilized exclusively by the HAL drivers built upon
them.
Core drivers reside below the HAL layer and must not depend on any HAL driver or file. The
only allowed dependency for core drivers is the device header file stm32tnxx.h.
To avoid confusion between user LL (Low-Layer) drivers and core drivers, the core driver
files must follow a specific naming convention: stm32tnxx_ppp_core.c/h (where "tn"
represents the series name and "ppp" represents the peripheral name eg. sdmmc).
Examples:
• stm32tnxx_otfdec_core.c/.h: the OTFDEC core driver used by the HAL XSPI driver
• stm32tnxx_dlyb_core.c/.h: The DeLay block core driver used by the HAL XSPI, SD
and MMC drivers
• stm32tnxx_fmc_core.c/.h : The FMC core driver used by the HAL SRAM, SDRAM,
NOR and NAND drivers
26

• stm32tnxx_sdmmc_core.c/.h: The SDMMC core driver used by the HAL SD, MMC
and SDIO drivers
• stm32tnxx_usb_core.c/.h: the USB core driver used by the HAL PCD and HCD
drivers
7.6. HAL utilities
These modules offer additional helper functions to support the HAL and LL drivers. For
example, the utils/i2c_timing folder contains the files stm32_utils_i2c.c and
stm32_utils_i2c.h, which provide functions to calculate the I2C timing values required by the
HAL_I2C_SetConfig and HAL_I2C_SetTiming functions in case of using the HAL and by the
LL_I2C_SetTiming function in case of using the LL.
7.7. LL driver files
STM32 LL (Low-Layer) drivers must provide a set of functions that allow direct access to the
hardware registers of the microcontroller. These drivers are designed for performance and
efficiency, offering a lightweight alternative to the HAL drivers. The LL drivers are
particularly useful in applications where low-level control and optimization are crucial.
File Naming Convention:
27

• Header File: stm32tnxx_ll_ppp.h
The LL (Low-Layer) drivers must be organized under an "LL" folder. This folder must
provide only the LL header files, such as stm32tnxx_ll_ppp.h.
7.8. HAL OS port modules
A HAL OS Abstraction Layer (OSAL) must be provided under the os_port folder in the
files stm32_hal_os.c and stm32_hal_os.h. The purpose of these files is to offer the HAL an
abstraction for OS services (OSAL). This includes semaphore services (create, take, release,
and delete), as well as non recursive mutex services (create, take, release, and delete).
The primary purpose of the HAL OS abstraction layer is to be used by the HAL PPP
Acquire/Release APIs when the USE_HAL_MUTEX define is set to 1. Additionally, the HAL
OSAL can be utilized by part drivers' IO interfaces or any applicative layer.
The stm32_hal_os.c and stm32_hal_os.h files must be provided with two implementations:
NO_OS and FreeRTOS. The STM32 HAL OS port is included within the HAL pack as a
component with two variants:
• NO_OS: This variant must have no other dependencies than the HAL and the CMSIS
core functions and APIs. It must rely on the Cortex services to set and clear a
semaphore object that is a U32 in a atomic way (depending from the cortex, it can use
Exclusive Load/Store instruction or critical sections by gating the interrupts)
• FreeRTOS: This variant is based on FreeRTOS semaphore and mutex services. It
depends on the corresponding FreeRTOS middleware CMSIS pack and components
The HAL OSAL must provide the following APIs:
API Name Description
HAL_OS_SemaphoreCreate () This method is used to create a new semaphore.
hal_os_status_t HAL_OS_SemaphoreCreate(hal_os_semaphore_t *p_sem)
HAL_OS_SemaphoreDelete () This method is used to delete the semaphore.
hal_os_status_t HAL_OS_SemaphoreDelete(hal_os_semaphore_t *p_sem)
This method is used to take the semaphore
HAL_OS_SemaphoreTake ()
hal_os_status_t HAL_OS_SemaphoreTake(hal_os_semaphore_t *p_sem,
uint32_t timeout_ms)
This method is used to release the semaphore
HAL_OS_SemaphoreRelease ()
hal_os_status_t HAL_OS_SemaphoreRelease(hal_os_semaphore_t *p_sem)
28

This method is used to create a new mutex.
HAL_OS_MutexCreate ()
hal_os_status_t HAL_OS_MutexCreate(hal_os_mutex_t *p_mutex)
This method is used to delete the mutex.
HAL_OS_MutexDelete ()
hal_os_status_t HAL_OS_MutexDelete(hal_os_mutex_t *p_mutex)
This method is used to take the mutex
HAL_OS_MutexTake ()
hal_os_status_t HAL_OS_MutexTake(hal_os_mutex_t *p_mutex, uint32_t
timeout_ms)
This method is used to release the mutex
HAL_OS_MutexRelease ()
hal_os_status_t HAL_OS_MutexRelease(hal_os_mutex_t *p_mutex)
7.9. HAL Time Base modules
The HAL time base management is built by default on the cortex system tick timer (systick)
and based on the following HAL services that are all defined as weak in the stm32tnxx_hal
module, so user can override them to use his own time base.
Function Description
__WEAK hal_status_t This function configures the time base
HAL_InitTick(hal_tick_freq_t tick_freq, frequency and interrupt priority.
uint32_t tick_priority)
• tick_freq Tick frequency with a
”hal_tick_freq_t“ type (to keep
current value, use global variable
uwTickFreq)
• tick_priority Tick interrupt priority
(to keep current value, use global
variable uwTickPrio)
__WEAK void HAL_IncTick(void) This function is called to increment time
base global variable uwTick
__WEAK void HAL_Delay(uint32_t delay_ms) This function provides minimum delay (in
milliseconds) based on variable
incremented.
__WEAK uint32_t HAL_GetTick(void) Provides a tick value in milliseconds.
uint32_t HAL_GetTickPrio(void) This function returns a tick priority
hal_tick_freq_t HAL_GetTickFreq(void) Return tick frequency
__WEAK void HAL_SuspendTick(void) Suspend Tick increment.
__WEAK void HAL_ResumeTick(void) Resume Tick increment
Note: The different time base variables are defined in the common HAL file
(stm32tnxx_hal.c/h) as exportable variables as follows:
▪ stm32tnxx_hal.c
29

volatile uint32_t uwTick;
uint32_t uwTickPrio = ((1UL << __NVIC_PRIO_BITS) - 1UL); /* Initial value: low priority */
hal_tick_freq_t uwTickFreq = HAL_TICK_FREQ_DEFAULT; /* 1KHz */
▪ stm32tnxx_hal.h
typedef enum
{
HAL_TICK_FREQ_10HZ = 100U, /*!< HAL tick frequency 10Hz */
HAL_TICK_FREQ_100HZ = 10U, /*!< HAL tick frequency 100Hz */
HAL_TICK_FREQ_1KHZ = 1U, /*!< HAL tick frequency 1kHz */
HAL_TICK_FREQ_DEFAULT = HAL_TICK_FREQ_1KHZ /*!< HAL tick default frequency: 1kHz */
} hal_tick_freq_t;
extern volatile uint32_t uwTick; /*!< HAL tick counter current value (unit: ms) */
extern uint32_t uwTickPrio; /*!< HAL tick interrupt priority */
extern hal_tick_freq_t uwTickFreq; /*!< HAL tick frequency */
As Real-time operating systems rely on the Cortex System Timer (SysTick) as RTOS time
base, the STM32 HAL drivers must provide components allowing the use of an RTC or a
Timer as HAL timebase. The relevant components are:
• stm32_hal_timebase_rtc_alarm.c
• stm32_hal_timebase_rtc_wakeup.c
• stm32_hal_timebase_tim.c
These components are ready-to-use, read-only pattern components that are not configurable
and do not require customization by the user.
Each of these components must provide an overridden implementation of the HAL Tick
functions, which can be based either on a TIMER, RTC alarm, or RTC wakeup time base.
The HAL_InitTick implementation must:
• Rely on either the code generation or standalone templates to redirect the used
resources (TIMER or RTC)
30

• Provide a dynamic calculation to allow generating a regular interrupt at the
required “tick_freq” frequency
The TIMER and RTC timebase modules require initialization functions of the corresponding
peripheral used as the time base, which can either be the result of code generation or provided
by the user starting from the given TIM and RTC templates. This is facilitated through the
following files:
• mx_rtc.c/.h
• mx_timx.c/.h
• stm32_hal_timebase.h
The mx_rtc.c/.h or mx_timx.c/.h files can either be generated based on user configuration of
these peripherals or provided by the user as customized copies of the templates. The link
between the stm32_hal_timebase_xxx.c files and the mx_rtc.h/mx_timx.h files is ensured
through the stm32_hal_timebase.h aliases.
Below is an example of how this can be achieved using a TIMER:
/**
************************************************************************
* @file stm32_hal_timebase_tim.c
...
*
*************************************************************************
*/
#include "stm32_hal.h"
#include "stm32_hal_timebase.h"
/*! Check HAL tick frequency value */
#define IS_TICK_FREQ(freq) (((freq) == HAL_TICK_FREQ_10HZ) \
|| ((freq) == HAL_TICK_FREQ_100HZ) \
|| ((freq) == HAL_TICK_FREQ_1KHZ))
/*! Check HAL tick priority value */
#define IS_TICK_PRIO(prio) ((prio) <= ((1UL << __NVIC_PRIO_BITS) - 1UL))
/* Private constants ---------------------------------------------------------*/
/* Private variables ---------------------------------------------------------*/
extern hal_tick_freq_t uwTickFreq;
extern uint32_t uwTickPrio;
static hal_tim_handle_t *hTIM = NULL;
/* Private function prototypes -----------------------------------------------*/
static hal_status_t find_psc_arr(uint32_t tim_freq, uint32_t Update_event_freq, uint32_t *psc, uint32_t
*arr);
static hal_status_t tim_timebase_config_tick(hal_tick_freq_t tick_freq);
#if defined(USE_HAL_TIM_REGISTER_CALLBACKS) && (USE_HAL_TIM_REGISTER_CALLBACKS == 1U)
void TimeBase_TIM_UpdateCallback(hal_tim_handle_t *htim);
#endif /* USE_HAL_TIM_REGISTER_CALLBACKS */
/* Private functions ---------------------------------------------------------*/
static hal_status_t tim_timebase_config_tick(hal_tick_freq_t tick_freq)
{
hal_status_t status;
31

hal_tim_config_t config;
uint32_t tim_freq = HAL_TIM_GetClockFreq(timebase_gethandle());
config.counter_mode = HAL_TIM_COUNTER_UP;
config.clock_division = HAL_TIM_CLK_DIVISION_DIV1;
config.repetition_counter = 0;
config.clock_sel.clock_source = HAL_TIM_CLK_INTERNAL;
status = find_psc_arr(tim_freq, (1000UL/ (uint32_t)tick_freq) , &config.prescaler, &config.period);
if(status == HAL_OK)
{
status= HAL_TIM_SetConfig(timebase_gethandle(), &config);
}
return status;
}
hal_status_t find_psc_arr(uint32_t tim_freq, uint32_t Update_event_freq, uint32_t *psc, uint32_t *arr)
{
/*
The update event period is calculated as follows:
Update_event = TIM_CLK/((PSC + 1)*(ARR + 1)*(RCR + 1))
Where: TIM_CLK = timer clock input
PSC = 16-bit prescaler register (0..65535)
ARR = 16/32-bit Autoreload register (1..65535)
RCR = 16-bit repetition counter
*/
uint32_t target;
uint32_t ppsc, parr;
if (Update_event_freq == 0 || tim_freq % Update_event_freq != 0)
{
return HAL_ERROR; // Invalid parameters
}
target = tim_freq / Update_event_freq;
for (ppsc = 0; ppsc <= UINT16_MAX; ppsc++)
{
if (target % (ppsc + 1) == 0)
{
parr = (target / (ppsc + 1)) - 1;
if (parr >= 1 && parr <= UINT16_MAX) // ARR min = 1, max = UINT16_MAX (65535)
{
*psc = (uint16_t)ppsc;
*arr = (uint16_t)parr;
return HAL_OK; // Found a valid pair
}
}
}
return HAL_ERROR;
}
/* Exported functions ---------------------------------------------------------*/
hal_status_t HAL_InitTick(hal_tick_freq_t tick_freq, uint32_t tick_priority)
{
hal_status_t status = HAL_ERROR;
ASSERT_DBG_PARAM(IS_TICK_FREQ(tick_freq));
ASSERT_DBG_PARAM(IS_TICK_PRIO(tick_priority));
if(HAL_TIM_GetState(timebase_gethandle()) == HAL_TIM_STATE_RESET)
{
if ( timebase_init() == NULL)
{
return HAL_ERROR;
32

}
}
else
{
HAL_TIM_Stop_IT(timebase_gethandle());
}
status = tim_timebase_config_tick(tick_freq);
if (status == HAL_OK)
{
#if defined(USE_HAL_TIM_REGISTER_CALLBACKS) && (USE_HAL_TIM_REGISTER_CALLBACKS == 1U)
HAL_TIM_RegisterUpdateCallback(timebase_gethandle(), TimeBase_TIM_UpdateCallback);
#endif /* USE_HAL_TIM_REGISTER_CALLBACKS */
uwTickFreq = tick_freq;
uwTickPrio = tick_priority;
HAL_CORTEX_NVIC_SetPriority(TIMEBASE_IRQ, (hal_cortex_nvic_preemp_priority_t)tick_priority,
HAL_CORTEX_NVIC_SUB_PRIORITY_0);
status = HAL_TIM_Start_IT(timebase_gethandle());
}
return status;
}
void HAL_SuspendTick(void)
{
HAL_TIM_Stop_IT(hTIM);
}
void HAL_ResumeTick(void)
{
HAL_TIM_Start_IT(hTIM);
}
#if defined(USE_HAL_TIM_REGISTER_CALLBACKS) && (USE_HAL_TIM_REGISTER_CALLBACKS == 1U)
void TimeBase_TIM_UpdateCallback(hal_tim_handle_t *htim)
#else
void HAL_TIM_UpdateCallback(hal_tim_handle_t *htim)
#endif /* USE_HAL_TIM_REGISTER_CALLBACKS */
{
STM32_UNUSED(htim);
HAL_IncTick();
}
Note: HAL_IncTick, HAL_GetTick and HAL_Delay does not need to be overridden when
using a TIMER or an RTC as a HAL time base, indeed these functions deals with the global
variables uwTick and uwTickFreq. The usage of these variables remains the same in all cases
(default timebase using CPU Systick or time base using a TIMER or the RTC)
7.10. HAL specific coding rules and convention
The HAL implementation must follow the coding rules [9]. The following additional
specific coding rules must also be respected.
• The HAL is based on a single time-base that provides the timeouts and delays method
needed by internal processes; Systick will be used as default time-base but it can be
replaced by any available peripheral that can provide the 1ms HAL time- base.
33

•  The rules relative to the use of RTOS must be respected across all the STM32Cube
firmware components :
| •  Re-entrancy.                            |     |     |
| ------------------------------------------ | --- | --- |
| •  Infinite loop has to be timeout based   |     |     |
| •  Shared resources have to be protected.  |     |     |
•  Timeout must be implemented to avoid blocking statements.
•  Timeout and delays are forbidden in Interrupt context. If required in some special cases
they must not be based on the HAL standard time base but rather on CPU cycle
counting to avoid priority conflicts, which might lead to same bottleneck situations.

7.11. HAL naming rules
| File names              |     |   stm32tnxx_hal_ppp (c/h)      |
| ----------------------- | --- | ------------------------------ |
| Module name             |     | HAL_PPP_ MODULE                |
| Function name           |     |  HAL_PPP_FeatureFunction_MODE  |
| Handle name             |     | hal_ppp_handle_t               |
| Exported Configuration  |     | hal_ppp_config_t               |
structure name
| Exported Enum name  |     | hal_ppp_enumname_t  |
| ------------------- | --- | ------------------- |
Exported Macros  HAL_PPP_{SUBBLOCK}_FUNCTION_BEHAVIOR ex: HAL_ADC_CALC_TEMPERATURE ()
Private Macros  {IS_}PPP_{SUBBLOCK}_FUNCTION_BEHAVIOR ex: IS_ADC_THRESHOLD
| Exported Defines  | HAL_PPP_CATEGORY_ITEM ex : HAL_GPIO_PIN_0   |     |
| ----------------- | ------------------------------------------- | --- |
| Private Defines   | PPP_CATEGORY_ITEM ex : I2C_XFER_TX_IT_MASK  |     |

The PPP prefix refers to the peripheral functional mode and not to the peripheral itself. For
example, for the USART peripheral, PPP can be USART, UART or SMARTCARD
depending on the peripheral mode.

•  No single/double underscore prefixes for any define/macro is allowed
Any HAL/LL define or macro must not start with underscore.  In addition, a define or macro
must be all capital.
#define HAL_PPP_DEFINE
#define LL_PPP_DEFINE
Note: this rule is already described in section “2.3 Constants, macros, types” of the
EmbSW C Coding standard” document [9].

•  Types must be lower case and must end with “_t”
Any HAL typedef must be lower case and must end with  “xxx_t”
•  Examples
o
HAL PPP Handle:
struct hal_ppp_handle_s;
typedef struct hal_ppp_handle_s hal_ppp_handle_t;
struct hal_ppp_handle_s
{
...
...
34

};
o HAL status type must be named “hal_status_t”
typedef enum
{
...
...
} hal_status_t;
• Header file guards underscore prefixes must be removed if existing.
Header files must come with guards to avoid double inclusion issues. The guards must be as
follow:
#ifndef FILENAME_H
#define FILENAME_H
....
#endif /* FILENAME_H */
Examples:
#ifndef STM32TNXX_HAL_PPP_H
#define STM32TNXX_HAL_PPP_H
....
#endif /* STM32TNXX_HAL_PPP_H */
• Use inline functions instead of big macros
As the Inline allows a better way to debug, it is recommended to use inline functions instead
of macros, which have consistency and still being optimized by compiler. The only allowed
exported macros are the helper macros (macros that help user to calculate a result or prepare a
data to be feed to the HAL ex: HAL_ADC_CALC_TEMPERATURE). Exported macros
(related to the HW registers access) are not allowed, and equivalent services must be added to
the LL layer or provided as inline HAL functions when no LL driver is provided pr the given
PPP.
• Use const keywords for non-modifiable pointers
The const qualifier is required to protect content for non-modified user input data pointers by
adding the qualifier before pointer type as follows: “const <type> p_[pointer_name]”
The const qualifier must be applied for the following cases:
o Configuration structure case
/**
* @brief Configures the PPP according to the user parameters.
* @param hppp Pointer to a hal_ppp_handle_t.
* @param p_config Pointer to the configuration structure.
* @retval HAL_OK
*/
hal_status_t HAL_PPP_SetConfig(hal_ppp_handle_t *hppp, const hal_ppp_config_t *p_config)
{
(...)
}
o User data buffers cases
/**
* @brief API description.
* @param hppp pointer to a hal_ppp_handle_tstructure.
* @param p_{pointer_name#i} pointer to non-modifiable data buffer.
* @param p_{pointer_name#j} pointer to modifiable data buffer.
* @param size amount of data to be sent and received in byte.
* @retval HAL_OK
*/
hal_status_t HAL_PPP_{Process#i}_IT(hal_ppp_handle_t *hppp,
35

const void *p_{pointer_name#i},
void *p_{pointer_name#j},
uint32_t size_byte)
{
(...)
}
o Pointer to non-modifiable data in any type case
/**
* @brief PPP handle structure definition
*/
typedef struct
{
(...)
const uint8_t *p_{pointer1_name}; /*!< Pointer to non-modifiable data buffer */
uint8_t *p_{pointer2_name}; /*!< Pointer to modifiable data buffer */
(...)
} hal_ppp_{type_name}_t;
• Exported functions, macros, defines and enum must be prefixed by HAL or LL
ITEM RULE EXAMPLES
HAL Exported structure must be prefixed by hal_ppp_handle_t
“hal_”
hal_ppp_config_t
LL Exported structure must be prefixed by “ll_” ll_dma_link_node_t
Fields within HAL/LL structures No prefix must be added !
HAL Exported enumeration Must be prefixed by hal_state_t
“hal_”
hal_ppp_state_t
LL Exported enumeration No enumeration must be deployed within LL !
Possible values within HAL Must be prefixed by HAL_DMA_HIGH_PRIORITY
enumeration “HAL_”
HAL_PPP_XXXXXXXXXXXX
Exported constant outside
enumeration
HAL exported APIs Must be prefixed by HAL_DMA_Start()
“HAL_”
HAL_PPP_xxxxxxxxx()
LL exported APIs (static inline APIs) Must be prefixed by LL_DMA_ConfigTransfer()
“LL_”
LL_PPP_xxxxxxxxxxx()
• Structure, parameters, and arguments functions names must be in lowercase.
ITEM RULE EXAMPLES
Typedef name In lower case hal_ppp_state_t, hal_ppp_t …
Names of parameters of All in lower typedef struct {
a structure cases
uint8_t param1;
uint32_t* p_buffer;
}
36

Argument in function In lower case hal_status_t HAL_PPP_{Process#i}_IT(hal_ppp_handle_t
*hppp,
const void *p_{pointer_name#i},
void *p_{pointer_name#j},
uint32_t size_byte)
• The HAL implementation must not use device RPN conditional defines.
For both HAL and LL drivers, it is prohibited to use the device RPN define as compile-time
conditional checks (e.g., #if defined(STM32U535xx)). Instead, the implementation must be
based on dedicated defines for peripherals, features, bit definition provided by the DFP header
files.
• Examples
o Using peripheral instance define
typedef enum
{
/** TIM1 external trigger is connected to I/O */
HAL_TIM_EXT_TRIG_TIM1_GPIO = LL_TIM_TIM1_ETRSOURCE_GPIO,
#if defined (COMP2)
/** TIM1 external trigger is connected to COMP2 output */
HAL_TIM_EXT_TRIG_TIM1_COMP2 = LL_TIM_TIM1_ETRSOURCE_COMP2,
#endif /* COMP2 */
/** TIM2 external trigger is connected to MSIK */
HAL_TIM_EXT_TRIG_TIM2_MSIK = LL_TIM_TIM2_ETRSOURCE_MSIK,
...
} hal_tim_ext_trig_src_t;
o Using PPP feature defines:
#if defined(ADC_MULTIMODE_SUPPORT)
static void adc_mm_reg_dma_data_transfer_stop_callback(hal_dma_handle_t *hdma);
#endif /* ADC_MULTIMODE_SUPPORT */
o Using register bit definition define:
#if defined(DMA2D_FGPFCCR_CSS)
IS_DMA2D_INPUT_YCBCR(input_color_mode) ...
#endif /* DMA2D_FGPFCCR_CSS */
This approach simplifies the maintenance of HAL and LL drivers when new derivatives of the
same series are introduced. In such cases, the Device Family Pack (DFP) should be updated
with the new device header file, which must include the necessary defines for peripherals and
features.
37

As a result, HAL and LL drivers will automatically support the new device derivatives without
requiring modifications, provided the peripherals and features remain consistent. Updates to
HAL and LL drivers are only necessary if the new derivative introduces new use cases or
features.
• Local Variable Table Size: If using a local variable that is an array, ensure the array
size does not exceed 128 bytes.
38

8. HAL/LL standalone templates
The STM32 HAL drivers must provide templates necessary for user applications when using
the HAL in standalone mode (without code generation). When using code generation, these
files will be automatically generated by the STM32 Tool according to the project
configuration. Thus, these template files are intended for direct use of the HAL in standalone
mode without code generation. These templates must be copied to the user application and
must be customized by the user according to the his needs.
These templates are provided in C code and can be classified into two categories:
• Templates that can be directly used with default behaviour:
o stm32tnxx_hal_conf.h: The STM32 HAL configuration file, intended to
customize the HAL modules' behaviour.
o stm32_ll.h: The STM32 LL entry inclusion file, including the LL driver header
files.
o stm32_assert.h: The STM32 HAL and LL assert header file, providing assert
macros for HAL and LL parameters and for HAL state.
• Templates that may need to be customized by the user according to their application:
o mx_rtc.c/mx_rtc.h: Provide an implementation of the RTC initialization when
the RTC is intended to be used as HAL time base.
39

o mx_timx.c/mx_timx.h: Provide an implementation of a Timer (TIMx)
initialization when the given TIMER is intended to be used as HAL time base.
Note that the exact TIM instance (TIMx) depends on the given STM32 series.
o stm32_hal_timebase.h: Provide an entry inclusion point for the
above mx_rtc.h and mx_timx.h. Provides also aliases to the user timer or RTC
“init” and “get handles” functions.
o stm32_hal_os.c/.h: Templates providing a skeleton for a custom HAL OSAL
implementation.
• Other templates: stm32_external_env.h Header file is a template provided b y the DFP
pack and must be copied and updated per platform specifications for standalone users
(not using STM32CubeMX2 Code Generation). It is not part of the HAL pack.
However, this file allows to to define the external oscillator values and other board
specific values such as the VDD value, the presence or not of a transceiver, etc.
When using STM32CubeMX2 with code generation, this file is generated according to
the user choices.
8.1. Common templates
8.1.1. HAL configuration file
The STM32 HAL configuration file, stm32tnxx_hal_conf.h, is designed to customize the
behaviour of the HAL modules. Users can utilize the provided file as-is, where all HAL
modules are enabled with their default settings. Alternatively, users have the flexibility to
customize the file based on their application's requirements. For example, they can enable only
the necessary HAL modules or modify the predefined settings to achieve the desired
functionality.
/** @file stm32tnxx_hal_conf.h */
/* ############## system/timebase config ##################### */
#define USE_HAL_TICK_INT_PRIORITY HAL_TICK_INT_LOWEST_PRIORITY /*!< tick interrupt priority (lowest by
default) */
#define USE_HAL_FLASH_PREFETCH 1U /*!< Enable Flash prefetch */
/* ############### HAL MUTEX usage activation ################# */
/* Used by the HAL PPP Acquire/Release APIs when the define USE_HAL_MUTEX is set to 1 */
#define USE_HAL_MUTEX 0U
/* ############### Run time parameter check activation ######## */
#define USE_HAL_CHECK_PARAM 0U
#define USE_HAL_SECURE_CHECK_PARAM 0U
/* ################ protection of state transition in thread safe activation ######## */
#define USE_HAL_CHECK_PROCESS_STATE 0U
40

/* ########################## PPP Config ############################## */
#define USE_HAL_PPP_MODULE 1U
#define USE_HAL_PPP_CLK_ENABLE_MODEL HAL_CLK_ENABLE_NO
#define USE_HAL_PPP_REGISTER_CALLBACKS 0U
#define USE_HAL_PPP_USER_DATA 0U
#define USE_HAL_PPP_GET_LAST_ERRORS 0U
#define USE_HAL_PPP_DMA 1U
#define USE_HAL_PPP_FEATURE1 1U
#define USE_HAL_PPP_FEATURE2 1U
#define USE_HAL_PPP_FEATURE3 1U
/* ex : */
/* ########################## ADC Config ############################## */
#define USE_HAL_ADC_MODULE 1U
#define USE_HAL_ADC_CLK_ENABLE_MODEL HAL_CLK_ENABLE_NO
#define USE_HAL_ADC_REGISTER_CALLBACKS 0U
#define USE_HAL_ADC_USER_DATA 0U
#define USE_HAL_ADC_GET_LAST_ERRORS 0U
#define USE_HAL_ADC_DMA 1U
/* ########################## SPI Config ############################## */
#define USE_HAL_SPI_MODULE 1U
#define USE_HAL_SPI_CLK_ENABLE_MODEL HAL_CLK_ENABLE_NO
#define USE_HAL_SPI_REGISTER_CALLBACKS 0U
#define USE_HAL_SPI_USER_DATA 0U
#define USE_HAL_SPI_GET_LAST_ERRORS 0U
#define USE_HAL_SPI_DMA 1U
#define USE_HAL_SPI_CRC 1U
...
The stm32tnxx_hal_conf.h must contain the following sections
Section Configuration defines Default value Description
System/Timebase USE_HAL_TICK_INT_PRIORITY HAL_TICK_INT_LOWEST_ Configures system tick
Configuration interrupt priority.
PRIORITY
USE_HAL_FLASH_PREFETCH 1 Configures flash prefetch
settings.
Note: the feature
availability depends on
the given STM32 series.
HAL Mutex USE_HAL_MUTEX 0 Enables or disables the
Usage Activation use of mutexes in HAL
PPP Acquire/Release
APIs.
41

| Runtime          | USE_HAL_CHECK_PARAM         | 0   | Enables or disables  |
| ---------------- | --------------------------- | --- | -------------------- |
| Parameter Check  |                             |     | runtime parameter    |
| Activation       |                             |     | checks.              |
|                  | USE_HAL_SECURE_CHECK_PARAM  | 0   | Enables or disables  |
secure parameter
checks.
| State Transition  |                              |     | Enables or disables      |
| ----------------- | ---------------------------- | --- | ------------------------ |
|                   | USE_HAL_CHECK_PROCESS_STATE  | 0   |                          |
| Protection in     |                              |     | protection of state      |
| Thread Safe       |                              |     | transitions in a thread- |
| Activation        |                              |     | safe manner.             |
| HAL PPP           | USE_HAL_PPP_MODULE           | 1   | Enables or disables the  |
| Configuration     |                              |     | PPP module.              |
USE_HAL_PPP_CLK_ENABLE_MODEL  HAL_CLK_ENABLE_NO  Configures the clock
enable model for PPP.
|     | USE_HAL_PPP_REGISTER_CALLBACKS  | 0   | Enables or disables  |
| --- | ------------------------------- | --- | -------------------- |
callback registration for
PPP.
|     | USE_HAL_PPP_USER_DATA  | 0   | Enables or disables user  |
| --- | ---------------------- | --- | ------------------------- |
data for PPP.
|     | USE_HAL_PPP_GET_LAST_ERRORS  | 0   | Enables or disables error  |
| --- | ---------------------------- | --- | -------------------------- |
retrieval for PPP.
|     | USE_HAL_PPP_DMA  | 1   | Enables or disables DMA  |
| --- | ---------------- | --- | ------------------------ |
for PPP.
|     | USE_HAL_PPP_FEATUREn  | x                                       | Enables or disables        |
| --- | --------------------- | --------------------------------------- | -------------------------- |
|     |                       | - 0: for enable/disable features Ex:    | feature n for PPP. Or set  |
|     |                       | USE_HAL_WWDG_HARDWARE_START             | the feature value.         |
|     |                       | - or a default value for multi-choices  |                            |
features Ex
USE_HAL_WWDG_TIME_UNIT feature
default value is
HAL_WWDG_TIME_UNIT_MS

8.1.2. stm32_ll.h header file

42

This file must provide a single inclusion entry point to all the LL drivers header files of a
given series. The file name must be agnostic i.e without the name of the series.
In the case of standalone usage, the stm32_ll.h includes all the LL driver header files of the
given series. In the case of code generation, this file contains only the selected LL driver
components. Users can utilize the copied file as is, where all LL drivers of the given STM32
family are included, or customize it to keep only the required LL driver's inclusion. This
flexibility allows users to optimize their application by including only the necessary LL
drivers, thereby improving maintainability.
/*** @file stm32_ll.h
/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef STM32_LL_H
#define STM32_LL_H
#ifdef __cplusplus
extern "C" {
#endif
/* Includes ------------------------------------------------------------------*/
#include "stm32tnxx_ll_adc.h"
#include "stm32tnxx_ll_bus.h"
#include "stm32tnxx_ll_comp.h"
#include "stm32tnxx_ll_cordic.h"
...
#include "stm32tnxx_ll_gtzc.h"
#include "stm32tnxx_ll_i2c.h"
#include "stm32tnxx_ll_icache.h"
#include "stm32tnxx_ll_iwdg.h"
#endif /* STM32_LL_H */
8.1.3. stm32_assert.h header file
The STM32 assert header file must provide assert macros for HAL parameters and HAL state
checks. Users can use the copied file as is, which provides an implementation of
the ASSERT_DBG_PARAM and ASSERT_DBG_STATE macros. However, they must
provide an implementation of
the assert_dbg_param_failed and assert_dbg_state_failed functions within their application.
Users also have the option to provide a custom implementation of the ASSERT macros, but
they need to keep the parameters as is. This ensures that the assert functionality is correctly
integrated and can handle parameter and state validation appropriately.
/** @file stm32_assert.h
...
/* Define to prevent recursive inclusion -------------------------------------*/
43

#ifndef STM32_ASSERT_H
#define STM32_ASSERT_H
#ifdef __cplusplus
extern "C" {
#endif
/* Exported macro ------------------------------------------------------------*/
#if defined(USE_ASSERT_DBG_PARAM)
#define ASSERT_DBG_PARAM(expr) ((expr) ? (void)0U : assert_dbg_param_failed((uint8_t *)__FILE__,
__LINE__))
/* Exported functions ------------------------------------------------------- */
void assert_dbg_param_failed(uint8_t *file, uint32_t line);
#else
#define ASSERT_DBG_PARAM(expr) ((void)0U)
#endif /* USE_ASSERT_DBG_PARAM */
#if defined(USE_ASSERT_DBG_STATE)
#define ASSERT_DBG_STATE(state,val) (((((uint32_t)(state)) & ((uint32_t)(val))) != 0U) ? \
(void)0U
: \
assert_dbg_state_failed((uint8_t *)__FILE__, __LINE__))
/* Exported functions ------------------------------------------------------- */
void assert_dbg_state_failed(uint8_t *file, uint32_t line);
#else
#define ASSERT_DBG_STATE(state,val) ((void)0U)
#endif /* USE_ASSERT_DBG_STATE */
#ifdef __cplusplus
}
#endif
#endif /* STM32_ASSERT_H */
8.2. Other templates impacting the HAL and LL behaviour: stm32_external_env.h header file
There are several defines that must be provided for adapting internal and external oscillator
values, as well as system configurations. These include:
• Internal Oscillator Values: Adaptations like HSI, MSI, etc.
• External Oscillator Values: Adaptations like HSE, LSE, etc.
• System Configuration: Values like VDD_VALUE.
The purpose of the stm32_external_env.h file is to provide the defines specific to the HW
platform/board, such as external oscillators.
This file Provided as a template in the DFP pack and must be copied and updated per
platform specifications for standalone users (not using STM32CubeMX2 Code
Generation).
If using STM32CubeMX2 Code Generation, the file is generated based on user selections.
This file is included in stm32tnxx.h under the switch USE_EXTERNAL_ENV. The
USE_EXTERNAL_ENV define, when needed, must be set in the project pre-processor.
#if defined(USE_EXTERNAL_ENV)
#include "stm32_external_env.h"
#endif /* USE_EXTERNAL_ENV */
44

To streamline the configuration, all internal oscillator values must be placed in the CMSIS
device file such as stm32u575xx.h file. The stm32tnxx_hal_conf.h must contain only the
configuration defines used by HAL. In stm32tnxx_hal_rcc.{c|h}, all the code linked to
external clocks must be handled under the <OSC_VALUE> pre-processor define.
Ex:
#if defined(HSE_VALUE)
typedef enum
{
HAL_RCC_HSE_ON = RCC_CR_HSEON, /*!< HSE clock
activation */
HAL_RCC_HSE_BYPASS = (RCC_CR_HSEBYP | RCC_CR_HSEON), /*!< External Analog
clock source for
HSE clock */
HAL_RCC_HSE_BYPASS_DIGITAL = (RCC_CR_HSEEXT | RCC_CR_HSEBYP | RCC_CR_HSEON), /*!< External Digital
clock source for
HSE clock */
} hal_rcc_hse_t;
#endif /* HSE_VALUE */
Note: As we move oscillator values inside the CMSIS file and stm32_external_env.h, these
defines must not be defined in any HAL and LL files such as stm32tnxx_ll_rcc.h file. This
ensures a cleaner separation of platform-specific configurations and HAL-specific settings,
improving maintainability and clarity
IMPORTANTE NOTE: The stm32_external_env.h is not part of the HAL driver files, it is
rather provided as a template in the DFP pack. It must be then copied once to the user example
or application and updated as per the platform specifications. In case of using STM32CubeMX2 with
code generation, this file is generated according to the user choices.
Note:
The implementation of the internal and external defines must use conditional define as
follows:
• For internal oscillator this allows user to define the required value at the compiler pre-
processor in case it needs to be adjusted.
/* file: stm32tnxxyy.h */
#if !defined(HSI_VALUE)
#define HSI_VALUE 144000000UL /*!< Value of the Internal oscillator in Hz*/
#endif
• For external oscillator and board dependent values, this allows user to define the
required values at the compiler pre-processor in case he don’t use the
stm32_external_env.h (the define USE_EXTERNAL_ENV is not set in the compiler
pre-processor).
/* file: stm32_external_env.h .h */
#if !defined(HSE_VALUE)
#define HSE_VALUE 8000000U /*!< Value of the External oscillator in Hz*/
#endif
8.3. HAL timebase templates
8.3.1. mx_timx.c/.h
45

The mx_timx.c/.h files are template files containing the HAL TIM (the one used as HAL
timebase) initialization, de-initialization, “get handle” and IRQ handler functions. These
templates are to be used when the application needs to use the TIMER "X" as a time base for
HAL (instead of the SysTick). When STM32CubeMX2 code generation is not used, these files
must be copied into the user space, and "X" in “timx” must be replaced according to the TIM
used by the application as the HAL time base.
The mx_timx.c/.h template file structure and offered functions must be identical to the
corresponding code generation for the TIM. It must contain:
• The init function: mx_timx_hal_init.
• The de-init function: mx_timx_hal_deinit.
• The “get handle function”: mx_timx_hal_gethandle
• The IRQHandler: TIMx_IRQHandler.
//mx_timx.h
/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef STM32_TIMx_H
#define STM32_TIMx_H
#ifdef __cplusplus
extern "C" {
#endif /* __cplusplus */
/* Includes ------------------------------------------------------------------*/
#include "stm32_hal.h"
hal_tim_handle_t *mx_timx_hal_init(void);
void mx_timx_hal_deinit(void);
hal_tim_handle_t *mx_timx_hal_gethandle(void);
void TIMx_IRQHandler(void);
#ifdef __cplusplus
}
#endif /* __cplusplus */
#endif /* STM32_TIMx_H */
46

// mx_timx.c
#include "mx_timx.h"
static hal_tim_handle_t hTIMx;
hal_tim_handle_t *mx_timx_hal_init(void)
{
if (HAL_TIM_Init(&hTIMx, HAL_TIMx) != HAL_OK)
{
return NULL;
}
HAL_RCC_TIMx_EnableClock();
/* Enable Timer update interrupt */
HAL_CORTEX_NVIC_SetPriority(TIMx_IRQn,
HAL_CORTEX_NVIC_PREEMP_PRIORITY_0,
HAL_CORTEX_NVIC_SUB_PRIORITY_0);
HAL_CORTEX_NVIC_EnableIRQ(TIMx_IRQn);
return &hTIMx;
}
void mx_timx_hal_deinit(void)
{
(HAL_TIM_DeInit();
HAL_RCC_TIMx_DisableClock();
HAL_CORTEX_NVIC_DisableIRQ(TIMx_IRQn);
}
hal_tim_handle_t *mx_timx_hal_gethandle(void)
{
return &hTIMx;
}
void TIMx_IRQHandler(void)
{
HAL_TIM_IRQHandler(&hTIMx);
}
Note: the mx_timx_hal_init must be limited to the call to HAL_TIM_Init, the TIM clock
enabling and the TIM NVIC enabling and priority setting. the mx_timx_hal_init must not
configure the timer that is done by the overridden “HAL_InitTick” function implemented in the
ready to use pattern “stm32_hal_timebase_tim.c
A standalone user (not using code generation) will need to copy these template files
(mx_timx.c/.h) and customize them according to their needs by changing the “x” in “timx” to
the used timer, for example, TIM2.
A user utilizing code generation will have the generated mx_timx.c/.h files ready and will not
need to copy and update these templates.
47

8.3.1. mx_rtc.c/.h
Same as the mx_timx.x/h, the mx_rtc.c/.h file must be provided as template files containing
the HAL RTC initialization to be used when need and RTC alarm or wakeup as HAL
timebase.
8.3.1. stm32_hal_timebase.h
The stm32_hal_timebase.h is a template file to be used when customizing the HAL “time
base” to use a TIMER or the RTC as a HAL time base. It is designed to include the
required file the mx_timx.h or mx_rtc.h.
It contains also redirection aliases to the TIMER “init” and “get handle” functions.
It is to be used by standalone users only (not using STM32CubeMX2). In case of using
STM32CubeMX2 with code generation, this file is generated according to the user
choices.
/**
******************************************************************************
* @file stm32_hal_timebase.h
...
*/
/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef STM32_HAL_TIMEBASE_H
#define STM32_HAL_TIMEBASE_H
#ifdef __cplusplus
extern "C" {
#endif /* __cplusplus */
/* Includes ------------------------------------------------------------------*/
/* When using a TIMER as a timebase :
update this line to include the header file of the corresponding TIMx:
example mx_tim6.h.
to be removed when using the RTC as time base */
#include "mx_timx.h"
/* keep it when using RTC ALARM or WAKEUP as a HAL timebase
to be removed when using a TIMER as a HAL time base */
#include "mx_rtc.h"
/******************************************************************************/
/* TIMEBASE ALIASES (private aliases) */
48

/******************************************************************************/
/*
When using a TIMER as a timebase : these aliases shall be updated to point to the
corresponding timx :
example #define timebase_gethandle mx_tim6_hal_gethandle
if not, it must be removed
*/
#define timebase_gethandle mx_timx_hal_gethandle
#define timebase_init mx_timx_hal_init
#define timebase_deinit mx_timx_hal_deinit
#define TIMEBASE_IRQ TIMx_IRQn
/*
When using RTC (Alarm or Wakeup) as a timebase : these aliases shall be kept.
if not, it must be removed
*/
#define timebase_init mx_rtc_hal_init
#define timebase_deinit mx_rtc_hal_deinit
#define TIMEBASE_IRQ RTC_IRQn
/* Exported functions ------------------------------------------------------- */
#ifdef __cplusplus
}
#endif /* __cplusplus */
#endif /* STM32_HAL_TIMEBASE_H */
49

8.4. HAL OS templates
8.4.1. stm32_hal_os.c/.h
The stm32_hal_os.c/.h files provide an empty implementation of the HAL OS abstraction.
These files serve as a skeleton of the required HAL OS APIs that must be implemented by
users who need to customize the HAL OSAL (Operating System Abstraction Layer)
implementation. This customization is necessary for users who are implementing a custom OS
or require a custom implementation of the HAL OSAL. By providing this skeleton, users have
a structured starting point to develop their own OS abstraction, ensuring compatibility and
integration with the HAL.
50

9. HAL/LL inclusion model
The stm32_hal.h file serves as the entry point header for any application using the HAL. It
includes the following files in the specified order:
• stm32tnxx_hal.h
• stm32_hal_os.h (under the conditional flag USE_HAL_MUTEX)
• Various HAL PPP modules (stm32tnxx_hal_ppp.h) under the conditional
flag USE_HAL_PPP_MODULE
o Note: HAL system modules such as RCC, GPIO, PWR, GTZC, and DMA must
be included first.
• stm32_assert.h (under the conditional
flags USE_ASSERT_DBG_PARAM or USE_ASSERT_DBG_STATE)
Note: The stm32_assert.h file is provided as a template and in case of STM32CubeMX2 code
generation not used, it must be copied into the application and customized by the user if
needed.
Each stm32tnxx_hal_ppp.h file must include the following:
• stm32tnxx_hal_def.h
• The required LL (Low-Layer) header file(s)
• The required core driver(s)
The stm32tnxx_hal_ppp.c must only include the stm32_hal.h.
51

The stm32tnxx_hal_def.h must include:
• HAL Configuration Defines: By including the stm32tnxx_hal_conf.h.
• Essential Types and Defines Related to STM32TN Devices: By including the
specific Device Family Pack (DFP) header file, such as stm32tnxx.h.
• Other Essential Types: By including standard headers like stddef.h and math.h.
This ensures that the stm32tnxx_hal_def.h file provides all necessary types and definitions
required for the given HAL drivers. Additionally, the user configuration is retrieved from the
lowest HAL header file in the inclusion model (stm32tnxx_hal_def.h) as it includes the
stm32tnxx_hal_conf.h. Thus, the HAL user configuration is propagated to all HAL driver
modules.
The core drivers reside below the HAL and must not be dependent on any HAL driver or file.
The only allowed dependency for a stm32tnxx_ppp_core.h core driver header file is to the
device header file stm32tnxx.h. This ensures that the core driver remains independent and can
function without relying on higher-level HAL components. The stm32tnxx_ppp_core.c must
include the stm32tnxx_ppp_core.h
52

10. HAL Data structures and types
10.1. HAL Peripherals instances
The HAL peripheral instances are represented as enumeration types. Each HAL PPP driver
includes an enumeration type that lists the supported instances for the specific driver within
the given series. These enumeration values for HAL PPP instances correspond to the
respective CMSIS peripheral physical instances. That helps the debug and ensure the right
types when selecting the instance.
• HAL driver instances
typedef enum
{
HAL_PPP1 = PPP1_BASE,
HAL_PPP2 = PPP2_BASE,
...
#if defined (PPPm)
HAL_PPPm = PPPm_BASE,
#endif
...
HAL_PPPn = PPPn_BASE,
} hal_ppp_t;
• CMSIS device instances
/* stm32tnabxx.h: a CMSIS device of the series */
#define PPP1_BASE (APB1PERIPH_BASE + 0x0000UL)
#define PPP2_BASE (APB1PERIPH_BASE + 0x0400UL)
...
...
#define PPPn_BASE (APB1PERIPH_BASE + 0x1400UL)
When an instance is available only on certain devices within a given series, the corresponding
HAL instance must be enclosed by a compilation switch. This switch corresponds to the
CMSIS peripheral physical instance as defined in the CMSIS header files for those specific
devices.
No changes are required for the LL drivers; they must continue using the HW PPP instances as
defined in the CMSIS device.
Within the HAL_PPP_Init function, the instance parameter must be of type hal_ppp_t and
must be stored in the corresponding instance parameter of the handle, with a check using an
assert (even if the parameter is an enumeration).
Within the configuration or process functions, a cast must be performed to transform the HAL
instance to the CMSIS instance (which is a pointer to the CMSIS PPP_TypeDef structure),
allowing access to the registers to read or write values. Two methods are possible:
• Using a local variable:
/* stm32tnxx_hal_ppp.c */
#define PPP_GET_INSTANCE (handle) ((PPP_TypeDef *)((uint32_t)(handle)->instance))
hal_status_t HAL_PPP_Func(hal_ppp_handle_t hppp, ...)
{
PPP_TypeDef *p_pppx;
p_pppx = PPP_GET_INSTANCE(handle);
LL_PPP_Func (p_pppx,...));
...
}
• Using a direct conversion when calling the LL or/and accessing a register
53

/* stm32tnxx_hal_ppp.c */
#define PPP_GET_INSTANCE (handle) ((PPP_TypeDef *)((uint32_t)(handle)->instance))
hal_status_t HAL_PPP_Func(hal_ppp_handle_t hppp, ...)
{
LL_PPP_Func (PPP_GET_INSTANCE(hppp),...));
...
}
Note: When converting from a HAL PPP instance, which is an enumeration, to a pointer to the
CMSIS instance, an intermediate cast to uint32_t is mandatory. This step is necessary to avoid
violating MISRA-C rule 11.7, which prohibits casting a non-integer type to a pointer.
10.2. HAL Peripherals handles
Almost all HAL drivers are based on handle objects, as described in the HAL data structure
section. These handles, denoted as hal_ppp_handle_t, are used to maintain the instance context
throughout all HAL processes for a given peripheral instance. When a peripheral HAL driver
is built around a handle, this object must be allocated and exist physically in RAM resources
for the driver usage lifetime.
The HAL handle object is allocated by the user at the application level; however, its content is
fully managed by the corresponding HAL driver. This means that the user should not access
the handle parameters directly, nor is it necessary to do so to initialize the HAL driver or start
a process. All handle fields are private and should not be accessed directly for reading or
writing by the application. The application must rely entirely on the HAL driver APIs to
configure the driver. Configuration parameters should be explicitly passed to the HAL driver
through the dedicated configuration APIs. When necessary, the HAL handle can store some of
these parameters for use during various process APIs.
All HAL drivers must provide a peripheral handle, except for shared and system peripherals,
where no handle or instance object is used. The peripherals concerned by this exception are:
• GPIO
• PWR
• RCC
• CORTEX(SYSTICK, NVIC, MPU, SCB)
• RTC/TAMP
• GTZC
• DBGMCU
• SYSCFG/SBS
• RAMCFG/RAMECC
• Flash Interface (handling the Flash OB and control, note that the Flash driver handling
the Program and erase processes must remain using a handle)
The HAL peripheral handle should be defined in stm32tnxx_hal_ppp.h and used for the
following purposes:
• Multi-instance support: Each peripheral hardware instance has its own handle,
ensuring no dependency between hardware instance resources.
54

• Peripheral process intercommunication: The handle is used to maintain shared data
resources between process routines, such as pointers, counters, DMA handles, and
state machines.
• Internal variables and pointers storage: The handle is also used to store private
variables and pointers within a HAL PPP driver.
• Storage of user data pointer: The handle provides a void pointer to associate
application-specific user data with the HAL PPP handle. Dedicated Set/Get user data
APIs must be provided.
Note: For RTC and TAMP, the HAL does not provide a handle, so no HAL instance
parameter is provided. The HAL implementation of RTC and TAMP directly uses the CMSIS
instance of these peripherals to read and write the appropriate registers. The LL RTC and
TAMP must continue providing the CMSIS instance as parameters.
typedef struct hal_ppp_handle_s hal_ppp_handle_t;
#if defined (USE_HAL_PPP_REGISTER_CALLBACK) && (USE_HAL_PPP_REGISTER_CALLBACKS == 1)
typedef void (*hal_ppp_cb_t)(hal_ppp_handle_t * hppp); /*!< pointer to a PPP callback functions */
#endif /* USE_HAL_PPP_REGISTER_CALLBACKS */
struct hal_ppp_handle_s
{
hal_ppp_t instance; /*!< Peripheral instance */
volatile hal_ppp_state_t global_state; /*!< PPP global state */
/* in case of several subinstances available and can be active in parallel:
Ex TIM Channels, channel_states[NB_CHANNELS] */
volatile {subinstance}_state_t {subinstance}_states[#nb_subinstance];
/* Or in case of one single subinstances that can be active at a time:
single subinstance state varibale, Ex ADC Channel, channel_State */
volatile {subinstance}_state_t {subinstance}_state; /*!< PPP {subinstance} state */
/* Or in case of multi process that can run in parallel, one state per process:
example UART TxState and RxState */
volatile {process#i}_state_t {process#i}_state; /*!< PPP {process#i} state */
volatile uint32_t param_i; /*!< Internal parameters */
...
#if defined (USE_HAL_PPP_GET_LAST_ERRORS) && (USE_HAL_PPP_GET_LAST_ERRORS == 1)
/* in case of single process at a time: one single variable storing the last errors */
volatile uint32_t last_error_codes;
/* in in case of several processes that can be active in parallel:
one variable storing the last errors per process */
volatile uint32_t last_{process#i}_error_codes;
#endif /* USE_HAL_PPP_GET_LAST_ERRORS */
#if defined (USE_HAL_PPP_DMA) && (USE_HAL_PPP_DMA == 1)
hal_dma_handle_t *hdma_i; /*!< Pointer to a specific process i DMA handle */
55

#endif /* USE_HAL_PPP_DMA */
#if defined (USE_HAL_PPP_USER_DATA) && (USE_HAL_PPP_USER_DATA == 1)
const void *p_user_data; /*!< User Data Pointer */
#endif /* USE_HAL_PPP_USER_DATA */
#if defined (USE_HAL_PPP_REGISTER_CALLBACK) && (USE_HAL_PPP_REGISTER_CALLBACKS == 1)
hal_ppp_cb_t p_event_i_cb; /*!< PPP event i callback */
hal_ppp_cb_t p_error_cb; /*!< Error callback */
#endif /* USE_HAL_PPP_REGISTER_CALLBACKS */
};
Field Description
instance Peripheral HAL hardware instance: one of the values defined in hal_ppp_t
enumeration type
global_state Peripheral global state
{sub-instance}_state Table of the sub-instances states. Applicable when several sub-
instances are available and can be active in parallel (Ex: TIMER channels)
Or Sub-instance state. Applicable when several sub-instances are available
but only one can be active at a time -Ex: the ADC channels)
{process#i}_state Process state. Applicable when several process can run in parallel. Ex
UART tx_State and rx_State
param_i Internal parameter(s): local data pointer, data counter…etc
used to store some required info needed by the processes (Ex: data pointer
and counter)
last_error_codes Applicable when only a single process at a time, this variable stores the last
occurred errors within the last executed process
last_{process#i}_error_codes Applicable when several process can run in parallel, one variable per
process to store the last occurred errors within the executed process#i
hdma_i Pointer to a specific process i DMA handle
Note DMA fields and dedicated HAL PPP APIs must be delimited by the
“USE_HAL_DMA_MODULE” (former
HAL_DMA_MODULE_ENABLED”) allowing to reduce footprint and
break the dependency with the HAL DMA driver when no
HAL_PPP_Process_DMA are used by the application
p_user_data Pointer to const void, used to allow the application associating specific user
data to the handle by mean of dedicated Set/Get user data APIs
p_event#i_cb PPP event i callback: a callback that can be registered by user and triggered
when the corresponding “event i” is reached asynchronously in case of
DMA or IT model (Ex: tx_cplt_callback)
p_error_cb a callback that can be registered by user and triggered when the
corresponding asynchronous error is encountered (DMA or IT model)
Note: the callback pointers are initialized to the weak empty callback during the HAL_PPP_Init. Also, the register
callback APIs checks that the call back are not null. As there is no check in the HAL_PPP_IRQHandler, the
56

callback points must never be set to null by any other way (example forcing the pointer stored inside the handle to
null)
The HAL handle must be forward declared as a structure hal_ppp_handle_s, followed by the
declaration of a hal_ppp_handle_t typedef. This approach allows the hal_ppp_handle_t type to
be used within the handle for callbacks.
typedef struct hal_ppp_handle_s hal_ppp_handle_t;
#if defined (USE_HAL_PPP_REGISTER_CALLBACK) && (USE_HAL_PPP_REGISTER_CALLBACKS == 1)
typedef void (*hal_ppp_cb_t)(hal_ppp_handle_t * hppp); /*!< pointer to a PPP callback functions */
#endif /* USE_HAL_PPP_REGISTER_CALLBACKS */
struct hal_ppp_handle_s
{
hal_ppp_t instance; /*!< Peripheral instance */
...
#if defined (USE_HAL_PPP_REGISTER_CALLBACK) && (USE_HAL_PPP_REGISTER_CALLBACKS == 1)
hal_ppp_cb_t p_event_i_cb; /*!< PPP event i callback */
hal_ppp_cb_t p_error_cb; /*!< Error callback */
#endif /* USE_HAL_PPP_REGISTER_CALLBACKS */
...
}
10.3. HAL configuration structures
The handle object must not store any Init structure. Instead, only the necessary inter-process
variables are stored within the handle.
Context: delta versus HAL1: The HAL PPP_InitTypeDef structure must be converted to
hal_ppp_config_t, which is provided as a parameter for the HAL_PPP_SetConfig and
HAL_PPP_GetConfig APIs (used to apply and retrieve a configuration, respectively).
The hal_ppp_config_t, also known as the global configuration structure, provides the essential
parameters needed to start a process. Depending on the peripheral, a process can be initiated
immediately after applying the global configuration (e.g., UART) or may require additional
sub-block configuration (e.g., TIM requires a global configuration and may also require at
least one channel configuration if used in output or input compare mode). In such cases, a sub-
block configuration structure, hal_ppp_{subblock}_{subinstance}_config_t, is provided (e.g.,
hal_tim_oc_channel_config_t). This sub-block configuration structure is intended to be used
with the sub-block Set/Get configuration APIs,
HAL_PPP_{SUBBLOCK}_SetConfig{Subinstance} and
HAL_PPP_{SUBBLOCK}_GetConfig{Subinstance} (e.g., HAL_TIM_OC_SetConfigChannel).
When additional features are provided by the peripheral that require configuration to control
the behavior or/and a specific feature of the peripheral, a dedicated feature configuration
structure must be provided as hal_ppp_{feature}_config_t (e.g., hal_tim_deadtime_config_t,
hal_spi_autonomousmode_config_t).
57

Example of global configuration structure
typedef struct
{
uint32_t prescaler;
hal_tim_counter_mode_t counter_mode;
uint32_t period;
hal_tim_clk_division_t clock_division;
uint32_t repetition_counter;
hal_tim_clock_sel_t clock_sel;
} hal_tim_config_t;
Example of a sub-block configuration structure
typedef struct
{
hal_tim_oc_mode_t mode;
uint32_t pulse;
} hal_tim_oc_compare_unit_config_t;
Example of a feature configuration structure
typedef struct
{
uint32_t crc_polynomial;
hal_spi_crc_length_t crc_length;
hal_spi_crc_tx_init_pattern_t crc_tx_init_pattern;
hal_spi_crc_rx_init_pattern_t crc_rx_init_pattern;
} hal_spi_crc_config_t;
10.4. HAL parameter types
• Finite params (including PPP instances) must be provided as enumeration types at HAL levels
• For HAL drivers, the defines lists used for user parameters must be provided as enumerations.
• The numerical values must correspond to the mask to be written or read in/from the
corresponding register (through the corresponding LL define or the CMSIS bit field defines
when no LL is provided for the given peripheral).
• This must be applied for HAL layer only, the LL must remain using defines as it must be close
to the CMSIS devices header files.
• within functions and structures that are using these parameters the given enumeration type
must be used instead of an UINT generic type.
• When the parameter (that is an enumeration type) is used as input (Ex: HAL_PPP_SetConfig
case) it must be used to read/modify/write the corresponding register.
o An additional cast (to uint32_t) is required to avoid compilation warning.
o Same when HAL is based on the LL
• When the parameter (that is an enumeration type) is used as output (Ex: HAL_PPP_GetConfig
case):
o An additional cast (to the enum type) is required to avoid compilation warning
o MISRA-C 2012 warning will be issued (R10.8 & R10.5) in any case as we are setting
an enumeration variable from a U32 (that theoretically can take values that are not in
the enumeration) . Note that he waivers are granted automatically by the eQA in this
case to avoid if/else or switch/case implementation that is too costly.
o
58

• When the parameters are intended to be provided to an API as a logical “OR” combination It
must be a numerical type (do not use enumerations)
• The HAL PPP driver must provide an enumeration type listing the PPP instances supported by
the given driver on the given series.
• The LL drivers must use the HW PPP instances as defined in the CMSIS device.
• In both cases, HAL enumeration or HAL defines list used for HW registers access, values must
be redirected to the equivalent LL defines this allow to direct usage of the LL APIs.
• All the user parameters must be checked using assert at HAL API implementation level, this is
applicable whatever the parameter type enumeration types or numerical.
10.5. HAL callback types
A dedicated type, hal_ppp_cb_t, must be provided for HAL PPP callbacks. This type is to be
used within the handle and within the HAL_PPP_RegisterXXXCallbacks APIs. For some
drivers, it is possible to have different callbacks with different prototypes. In such cases, a
callback type for each prototype should be provided.
For example, in the case of HAL TIM:
#if defined (USE_HAL_TIM_REGISTER_CALLBACKS) && (USE_HAL_TIM_REGISTER_CALLBACKS == 1)
/** HAL TIM generic callback pointer definition */
typedef void (* hal_tim_cb_t) (hal_tim_handle_t *);
/** HAL TIM callback pointer definition with channel parameter */
typedef void (* hal_tim_channel_cb_t) (hal_tim_handle_t *, hal_tim_channel_t);
#endif /* USE_HAL_TIM_REGISTER_CALLBACKS */
59

11. HAL drivers’ APIs
The public HAL APIs are composed of five API categories for each peripheral:
• Initialization and De-initialization APIs:
o HAL_PPP_Init: The first API to be called to initialize a given instance of the
HAL PPP driver. Associates a given peripheral instance with the handle object
and initializes this software object. Does not configure the peripheral;
configuration is handled by separate configuration APIs.
o HAL_PPP_DeInit: Deinitializes the given HAL PPP driver linked to a specific
PPP instance and stops or aborts any ongoing process and resets the HAL PPP
states.
• Configuration APIs: Allow the user to configure the peripheral according to their
parameters.
• Processing APIs: Offer a set of functions designed to manage data processing for
various peripherals in a microcontroller.
• Optional Features and Control APIs: Provide additional functionalities and control
mechanisms for the peripherals.
• Peripheral State Methods: Permit retrieval of the peripheral's states and error codes at
runtime.
Common API Name Description
HAL_Init() Initializes the HAL module and make device ready for other HAL modules operation.
It configures the HAL time base and the system generic features (NVIC priority grouping
configuration, flash prefetch ...)
hal_status_t HAL_Init(void);
HAL_DeInit() De-initialize the HAL module. It resets all peripherals (except system ones needed for code
execution)
hal_status_t HAL_DeInit(void);
HAL_GetVersion() Returns the HAL revision.
uint32_t HAL_GetVersion(void);
HAL_GetDeviceUniqueID() Return the device unique identification
hal_status_t HAL_GetDeviceUniqueID(hal_device_uid_t *uid);
HAL_PPP_Init() This method is used to initialize a HAL driver handle and associate it to a HAL PPP physical
instance. Eg:
hal_status_t HAL_UART_Init(hal_uart_handle_t *huart,
hal_uart_t instance);
HAL_PPP _DeInit() This method is used to abort/stop any ongoing process and restore the reset state of the HAL
PPP driver. This ends the usage sequence of the given HAL PPP handle. Eg:
void HAL_UART_DeInit(hal_uart_handle_t *huart);
HAL_PPP_SetConfig This method is used to configure the PPP peripheral according to the user parameters. Eg:
60

hal_status_t HAL_UART_SetConfig(hal_uart_handle_t *huart, const
hal_uart_config_t *p_config);
HAL_PPP_GetConfig This method is used to retrieve the PPP peripheral configuration. Eg:
void HAL_UART_GetConfig(const hal_uart_handle_t *huart,
hal_uart_config_t *p_config);
HAL_PPP_SetItem This method is used to change/update an item of the PPP peripheral configuration (once the
HAL_PPP_SetConfig is done) Eg:
hal_status_t HAL_UART_SetParity( const hal_uart_handle_t *huart,
hal_uart_parity_t parity);
HAL_PPP_GetItem This method is used to retrieve the value of a PPP peripheral configuration item. Eg:
hal_uart_parity_t HAL_UART_GetParity( const hal_uart_handle_t
*huart);
HAL_PPP_{SUBBLOCK_}SetConfig{Sub This method is used to configure a sub-block of the PPP peripheral. The configuration can
instance} be relative to a sub-instance. Eg:
hal_status_t
HAL_TIM_IC_SetConfigChannel(hal_tim_handle_t *htim,
hal_tim_channel_t
channel, const hal_tim_ic_channel_config_t
*p_config);
HAL_PPP_{SUBBLOCK}_GetConfig{Su This method is used to retrieve the configuration of a sub-block of the PPP peripheral. The
binstance} configuration can be relative to a sub-instance. Eg:
void
HAL_TIM_IC_GetConfigChannel(const hal_tim_handle_t *htim,
hal_tim_channel_t
channel, hal_tim_ic_channel_config_t
*p_config);
HAL_PPP_{SUBBLOCK}_Set{Subinstanc This method is used to Set an item of a sub-block of the PPP
e}Item()
peripheral. It can be relative to a sub-instance. Eg:
hal_status_t HAL_TIM_IC_SetChannelSource(
const hal_tim_handle_t *htim,
hal_tim_channel_t channel,
hal_tim_channel_src_t channel_src);
HAL_PPP_{SUBBLOCK}_Get{Subinstan This method is used to retrieve a configuration item of a sub-block of
ce}Item()
the PPP peripheral. It can be relative to a sub-instance. Eg:
hal_tim_channel_src_t HAL_TIM_IC_GetChannelSource(
const hal_tim_handle_t
*htim, hal_tim_channe
l_t channel);
HAL_PPP_SetFeature() This method is used to set a given additional feature parameter(s). In this case the feature
takes effect immediately and requires additional action from the user to enable nor disable
it. Eg:
hal_status_t HAL_I2C_SetDigitalFilter(hal_i2c_handle_t *hi2c,
uint32_t value);
HAL_PPP_GetFeature() This method is used to retrieve a given additional feature parameter(s). Such feature takes
effect immediately and does require additional action from the user to enable or disable it.
Eg:
uint32_t HAL_I2C_GetDigitalFilter(const hal_i2c_handle_t *hi2c);
61

HAL_PPP_SetConfigFeature() This method is used to configure a feature. In this case the feature does not take effect
immediately and requires additional explicit action from the user to enable or disable it. Eg:
hal_status_t HAL_I2C_SetConfigOwnAddress2(hal_i2c_handle_t *hi2c,
uint32_t addr, hal_i2c_own_addr2_mask_t mask);
HAL_PPP_GetConfigFeature() This method is used to retrieve the configuration of a feature. Such features take effect
immediately and does require additional action from the user to enable or disable it. The
status of the feature enabled or disable can also be retrieved using the associated
HAL_PPP_IsEnabledFeature(). Eg:
void HAL_I2C_GetConfigOwnAddress2(const hal_i2c_handle_t *hi2c,
uint32_t *addr, hal_i2c_own_addr2_mask_t *mask);
HAL_PPP_EnableFeature() This method is used to enable a feature. The feature can be configurable, in this case a
HAL_PPP_SetConfigFeature() is provided.
HAL_PPP_DisableFeature() This method is used to disable a feature. The feature can be configurable, in this case a
HAL_PPP_SetConfigFeature() is provided. Eg:
hal_status_t HAL_I2C_DisableOwnAddress2(
hal_i2c_handle_t *hi2c);
HAL_PPP_IsEnabledFeature() This method is used to check if the feature is enabled. Eg:
hal_i2c_analog_filter_status_t HAL_I2C_IsEnabledAnalogFilter(const
hal_i2c_handle_t *hi2c);
HAL_PPP_SetProcess#iDMA() This method is used to link a HAL DMA handle to a HAL PPP handle to be used for a given
Process #i. Eg:
hal_status_t HAL_UART_SetTxDMA(hal_uart_handle_t *huart,
hal_dma_handle_t *hdma_tx);
HAL_PPP_Process#i() This method is used to run a given process in polling/blocking model.
Eg:
hal_status_t HAL_UART_Transmit(hal_uart_handle_t *huart,
const void *p_data,
uint32_t size_byte,
uint32_t timeout_ms);
HAL_PPP_ Process#i_IT() This method is used to run a given process in Async Interrupt based model. Eg:
hal_status_t HAL_UART_Transmit_IT(hal_uart_handle_t *huart,
const void *p_data,
uint32_t size_byte);
HAL_PPP_ Process#i _DMA() This method is used to run a given process in Async DMA based model. Eg:
hal_status_t HAL_UART_Transmit_DMA(hal_uart_handle_t *huart,
const void *p_data,
uint32_t size_byte);
HAL_PPP_ Process#i_IT_Opt() This method is used to run a given process in Async Interrupt based model with the
possibility to specify the desired optional interrupts. Eg:
hal_status_t HAL_UART_Transmit_IT_Opt(
hal_uart_handle_t *huart,
const void *p_data, uint32_t size_byte,
uint32_t interrupts);
HAL_PPP_ Process#i_DMA_Opt() This method is used to run a given process in Async DMA based model with the possibility
to specify the desired optional interrupts at PPP side and DMA side. Eg:
hal_status_t HAL_UART_Transmit_DMA_Opt(
hal_uart_handle_t *huart,
const void *p_data, uint32_t size_byte,
uint32_t interrupts);
62

HAL_PPP_Abort() This method is used to abort an ongoing async process(es) i.e IT or DMA based process.
HAL_PPP_AbortProcess#i() This method cannot abort a polling-based process.
This HAL_PPP_Abort is a blocking function. When this method returns, the process has
been effectively aborted. Eg:
hal_status_t HAL_UART_Abort(hal_uart_handle_t *huart);
hal_status_t HAL_UART_AbortTransmit(hal_uart_handle_t *huart);
hal_status_t HAL_UART_AbortReceive(hal_uart_handle_t *huart);
HAL_PPP_Abort_IT() This method is used to abort an ongoing async process(es) i.e IT or DMA based process.
HAL_PPP_AbortProcess#i_IT() This method cannot abort a polling-based process.
This function is non-blocking one. It initiates the abort and returns immediately. Later, when
the process has been effectively aborted, the user receives a dedicated abort completion
callback. Eg:
hal_status_t HAL_UART_Abort_IT(hal_uart_handle_t *huart);
hal_status_t HAL_UART_AbortTransmit_IT(hal_uart_handle_t *huart);
hal_status_t HAL_UART_AbortReceive_IT(hal_uart_handle_t *huart);
HAL_PPP_IRQHandler() This method is used to handle all the interrupts of a given peripheral instance managed by a
given HAL PPP handle. Eg:
void HAL_UART_IRQHandler(hal_uart_handle_t *huart);
Note: additional specialized HAL PPP IRQhandler could be provided to handle a set of
interrupts for a given process or scope. Eg:
void HAL_TIM_UPD_IRQHandler(hal_tim_handle_t *htim);
HAL_PPP_Event#i_IRQHandler() These methods can be provided in addition to the global HAL_PPP_IRQHandler() that
HAL_PPP_Feature#i_IRQHandler() handle all interrupts. The goal of these additional methods is to provide specialized HAL
HAL_PPP_Process#i_IRQHandler() IRQ handlers for a given event, Feature, process or subblock to improve the final application
HAL_PPP_SUBBLOCK#i_IRQHandler() behavior regarding the interrupts management (checking and handling only required
interrupts versus the application scenario and needs). E.g
Event specialized IRQ handler:
void HAL_LTDC_LineDetection_IRQHandler(hal_ltdc_handle_t *hltdc);
Feature specialized IRQ handler:
void HAL_NVM_ECC_IRQHandler(hal_nvm_handle_t *hnvm)
Process specialized IRQ handler:
void HAL_FLASH_ProgramByAddr_IRQHandler(hal_flash_handle_t
*hflash);
Subblock specialized IRQ handler:
void HAL_GFXTIM_WDG_IRQHandler(hal_gfxtim_handle_t *hgfxtim);
HAL_PPP_Event#i_Callback() This is a default callback for a given event #i implemented as a Weak function in the HAL
PPP. Eg:
void HAL_UART_TxCpltCallback(hal_uart_handle_t *huart);
HAL_PPP_RegisterEvent#iCallback() This method is used to register a user callback for the given event #i. Eg:
hal_status_t HAL_UART_RegisterTxCpltCallback(
hal_uart_handle_t *huart,
hal_uart_cb_t p_callback);
HAL_PPP_ReadXxxxData() These methods allow to read and write data from/to the peripherals.
HAL_PPP_WriteXxxxData() Note that these APIs naming is used when it comes to reading or writing data from/to the
peripherals (for example reading ADC conversion value or read/write a TAMP backup
register). The APIs HAL_PPP_SetFeature/ HAL_PPP_GetFeature (as described above) are
used to set or get a feature/config value (not for data)
Eg.
TAMP:
63

< void
HAL_TAMP_WriteBackupRegisterData(hal_tamp_backup_register_idx_t
reg_idx, uint32_t data_32bit);
uint32_t
HAL_TAMP_ReadBackupRegisterData(hal_tamp_backup_register_idx_t
reg_idx);
HAL_PPP_AcquireBus() These methods are provided for HAL PPP drivers of the bus and communication interface
HAL_PPP_ReleaseBus() peripherals ( I2C, USART, UART, SPI, SAI, I2S, PSSI, CAN/FDCAN, I3C …).
These methods are respectively used to take and release dedicated HAL OS semaphore
stored into the HAL PPP handle. these methods are available under the compilation switch
USE_HAL_MUTEX.
Eg:
#if defined(USE_HAL_MUTEX) && (USE_HAL_MUTEX == 1)
hal_status_t HAL_UART_AcquireBus(hal_uart_handle_t *huart, uint32_t
timeout_ms);
hal_status_t HAL_UART_ReleaseBus(hal_uart_handle_t *huart);
#endif /* USE_HAL_MUTEX */
HAL_PPP_GetClockFreq() This method is provided for analog, audio and communication and Graphical peripherals that
have a kernel clock + The TIMER peripherals (TIM, LPTIM, HRTIM).
This method is used to retrieve the frequency at which the peripheral is running which may
be required for the application (Ex in case of the TIMER this info is needed to calculate the
frequency of an input signal).
Eg:
uint32_t HAL_TIM_GetClockFreq(const hal_tim_handle_t *htim);
HAL_PPP_SetUserData() This method is used to store a user data pointer into the HAL PPP handle. Eg:
void HAL_UART_SetUserData(hal_uart_handle_t *huart,
const void *p_user_data);
HAL_PPP_GetUserData() This method is used to retrieve the user data pointer from the HAL PPP handle. Eg:
const void *HAL_UART_GetUserData(const hal_uart_handle_t *huart);
H AL_PPP_GetState() This Method is used to retrieve the HAL PPP driver state. Eg:
hal_uart_state_t HAL_UART_GetState(const hal_uart_handle_t *huart);
HAL_PPP_GetProcess#iState() This method is provided in case of several processes can run in parallel. It is used to retrieve
a given process #i state. Eg:
hal_uart_tx_state_t HAL_UART_GetTxState(const hal_uart_handle_t
*huart);
hal_uart_rx_state_t HAL_UART_GetRxState(const hal_uart_handle_t
*huart);
HAL_PPP_GetLastErrorCodes() This method is used to retrieve the occurred errors since the last process execution started.
Eg:
uint32_t HAL_TIM_GetLastErrorCodes(const hal_tim_handle_t *htim);
HAL_PPP_GetInstance() This method is used to retrieve the HAL Peripheral instance associated to the given handle.
Eg:
Hal_i2c_t HAL_I2C_GetInstance(const hal_i2c_handle_t *hi2c);
HAL_PPP_GetLLInstance() This method is used to retrieve the CMSIS/LL Peripheral instance equivalent to the HAL
instance . Eg:
• Case of a HAL driver using a handle (HAL I2C)
I2C_TypeDef *HAL_I2C_GetLLInstance(const hal_i2c_handle_t *hi2c);
• Case of a HAL driver not using a handle (HAL RAMCFG)
64

RAMCFG_TypeDef *HAL_RAMCFG_GetLLInstance(hal_ramcfg_t instance);
HAL_PPP_EnableClock() These methods are used to respectively enable/disable and check the status of the clock of
HAL_PPP_DisableClock() the peripheral instance associated to the given handle. The implementation of these APIs
HAL_PPP_IsEnabledClock() should rely on the HAL RCC.
Eg:
typedef enum
{
HAL_UART_CLOCK_DISABLED = 0U,
HAL_UART_CLOCK_ENABLED = 1U,
} hal_uart_clock_status_t;
hal_status_t HAL_UART_EnableClock(hal_uart_handle_t *huart);
hal_status_t HAL_UART_DisableClock(hal_uart_handle_t *huart);
hal_uart_clock_status_t HAL_UART_IsEnabledClock(hal_uart_handle_t
*huart);
HAL_PPP_NVIC_EnableIRQ() These methods are used to respectively enable/disable and check the status of the NVIC IRQ
HAL_PPP_NVIC_DisableIRQ() of the peripheral instance associated to the given handle. Eg:
HAL_PPP_NVIC_IsEnabledIRQ()
typedef enum
{
HAL_UART_NVIC_IRQ_DISABLED = 0U,
HAL_UART_NVIC_IRQ_ENABLED = 1U,
} hal_uart_nvic_irq_status_t;
hal_status_t HAL_UART_NVIC_EnableIRQ(hal_uart_handle_t *huart);
hal_status_t HAL_UART_NVIC_DisableIRQ(hal_uart_handle_t *huart);
hal_uart_nvic_irq_status_t
HAL_UART_NVIC_IsEnabledIRQ(hal_uart_handle_t *huart);
HAL_PPP_IsActiveFlag() These HAL methods must be provided in the HAL as static inline only in case there is no LL
HAL_PPP_ClearFlag() driver for the corresponding peripheral. If there is an LL driver the flags (check/clear) and
HAL_PPP_EnableIT() Interrupts (enabling/disabling and check) must be handled by the LL driver as specified in
HAL_PPP_DisableIT() the “LL drivers chapter of this specification
HAL_PPP_IsEnabledIT()
E.g
__STATIC_INLINE uint32_t HAL_LTDC_IsActiveFlag(const
hal_ltdc_handle_t *hltdc, uint32_t flag) {...}
__STATIC_INLINE void HAL_LTDC_ClearFlag(hal_ltdc_handle_t *hltdc,
uint32_t flag) {...}
__STATIC_INLINE void HAL_LTDC_EnableIT(hal_ltdc_handle_t *hltdc,
uint32_t interrupt) {...}
__STATIC_INLINE void HAL_LTDC_DisableIT(hal_ltdc_handle_t *hltdc,
uint32_t interrupt) {...}
65

__STATIC_INLINE uint32_t HAL_LTDC_IsEnabledIT(const
hal_ltdc_handle_t *hltdc, uint32_t interrupt) {...}
66

11.1. Initialization and deinitialization APIs
11.1.1. HAL PPP initialization
The HAL_PPP_Init function must be the first API called to initialize a given instance of the
HAL PPP driver. The scope of the HAL_PPP_Init API is limited to associating a given
peripheral instance with the handle object and initializing this latter software object.
The HAL_PPP_Init function does not configure the peripheral; this is the purpose of the
configuration API. However, HAL_PPP_Init can activate the peripheral clock upon user
demand using a dedicated compilation switch.
The HAL_PPP_Init APIs must perform the following actions:
• Check Handle and the PPP instance validity: using ASSERTS
• Associate the HAL PPP instance with the HAL PPP handle.
• If the compilation switch USE_HAL_PPP_CLK_ENABLE_MODEL is set to a value
equal to or greater than HAL_CLK_ENABLE_PERIPH_ONLY, enable the PPPi clock
using the dedicated LL or HAL PPPi clock enabling APIs. If the given peripherals have
dependencies with the system and PWR, and the compilation switch is set
to HAL_CLK_ENABLE_PERIPH_PWR_SYSTEM, then the additional PWR and system
components needed to make the peripheral work must be enabled.
• Set default callbacks to the weak default callbacks. Callbacks can be updated after
initialization if needed using HAL_PPP_RegisterEventiCallback APIs when this feature is
enabled.
• Initialize the handle fields (states or any other internal fields used during various possible
HAL processes) including initializing the "User Data pointer" (p_user_data) to NULL and
reseting the last_error_codes variable storing the last errors
• Set the sub-instances or processes states if any to RESET, and finally, set the global HAL
PPP state within the handle to HAL_PPP_STATE_INIT, indicating that the HAL PPP
driver is initialized for the current handle object but not yet ready to start a process, as it
requires configuration
/**
* @brief Initialize the PPP handle and associate an instance.
* @param hppp pointer to a hal_ppp_handle_t structure.
* @param instance one of the values of the enumeration hal_ppp_t .
* @retval HAL_OK HAL PPP initialization done
* @retval HAL_INVALID_PARAM when the hppp handle is NULL
*/
hal_status_t HAL_PPP_Init(hal_ppp_handle_t *hppp, hal_ppp_t instance)
{
/* Check the PPP handle allocation */
ASSERT_DBG_PARAM((hppp != NULL));
/* Check the PPP instance */
ASSERT_DBG_PARAM(IS_PPP_INSTANCE((PPP_TypeDef *) ((uint32_t)instance)));
#if defined(USE_HAL_CHECK_PARAM) && (USE_HAL_CHECK_PARAM ==1)
/* Check the handle struct pointer */
if(hppp == NULL)
{
return HAL_INVALID_PARAM;
}
#endif /* USE_HAL_CHECK_PARAM */
hppp->instance = instance;
#if defined (USE_HAL_PPP_REGISTER_CALLBACKS) && (USE_HAL_PPP_REGISTER_CALLBACKS == 1)
/* Init the PPP Callback settings */
hppp->p_event_i_cb = HAL_PPP_EventiCallback; /* Event_i callback reset */
67

...
hppp->p_error_cb = HAL_PPP_ErrorCallback; /* Error callback reset */
#endif /* USE_HAL_PPP_REGISTER_CALLBACKS */
/* Init the handle internal parameters */
hppp->param_i = #VALUE;
...
#if defined (USE_HAL_PPP_USER_DATA) && (USE_HAL_PPP_USER_DATA == 1)
/* Init the user data pointer to NULL */
hppp->p_user_data = NULL;
#endif
...
...
#if defined (USE_HAL_PPP_GET_LAST_ERRORS) && (USE_HAL_PPP_GET_LAST_ERRORS == 1)
/* Reset the last_error_codes variable storing the last errors */
hspi->last_error_codes = HAL_PPP_ERROR_NONE;
#endif /* USE_HAL_PPP_GET_LAST_ERRORS */
#if defined(USE_HAL_PPP_CLK_ENABLE_MODEL) && (USE_HAL_PPP_CLK_ENABLE_MODEL >=
HAL_CLK_ENABLE_PERIPH_ONLY)
/* Enable the PPP Peripheral Clock */
switch (hppp->instance)
{
#if defined(PPP1)
case HAL_SPI1:
/* Enable Clock */
LL_APB2_GRP1_EnableClock(LL_APB2_GRP1_PERIPH_PPP1);
break;
#endif /* PPP1 */
...
}
#if defined (USE_HAL_PPP_DMA) && (USE_HAL_PPP_DMA == 1)
hppp->hdma_i = NULL; /*!< Init the process i DMA handle to NULL */
#endif /* USE_HAL_PPP_DMA */
/* Init the subinstances states when available */
hppp->{subinstance}_states[0] = HAL_PPP_{SUBINSTANCE}_STATE_RESET;
...
hppp->{subinstance}_states[#nb_subinstance] = HAL_PPP_{SUBINSTANCE}_STATE_RESET;
/* Or Init the subinstance single state variable when available */
hppp->{subinstance}_state = HAL_PPP_{SUBINSTANCE}_STATE_RESET;
/* Or Init the processes states when available */
hppp->{process#i}_state = HAL_PPP_STATE_{PROCESS#i}_RESET;
...
hppp->{process#j}_state = HAL_PPP_STATE_{PROCESS#i}_RESET;
/* Init the global state */
hppp->global_state = HAL_PPP_STATE_INIT;
return HAL_OK;
}
11.1.2. HAL PPP deinitialization
The HAL_PPP_DeInit service should be used to de-initialize a given instance of the HAL PPP
driver when a HAL_PPP_Init service exists. The HAL_PPP_DeInit service must perform the
following actions:
• Check Handle and the PPP instance validity: using ASSERTS
• Stop Current Operations:
o Invoke the required private routines to stop or abort any ongoing process.
This includes disabling the IP, disabling interrupts, and clearing flags.
68

o Alternatively, implement the stop/abort directly within HAL_PPP_DeInit
using a sequence of LL calls or by writing to the required registers/fields.
o Note: Do not call public APIs HAL_PPP_Stop or HAL_PPP_Abort to avoid
state machine conflicts as each public API has its own state checks.
o Note: the stop and abort of ongoing process must take into consideration
stopping aborting the DMA if used by the given driver and ongoing process
(meaning that corresponding DMA handle used by the PPP handle must go
back to IDLE state once the parent HAL PPP is de-initialized.
• Delete Bus Semaphore: If USE_HAL_MUTEX is set to 1, delete the bus semaphore
for the bus drivers' category.
• Reset Handle State: Reset the handle's global state, process state, and sub-
instance(s) states (if any).
o Set the global HAL PPP state and sub-instance(s) within the handle to
HAL_PPP_STATE_RESET, indicating that the HAL PPP driver is de-
initialized for the current handle object.
• A new initialization and configuration sequence is required to reuse this handle
object. Therefore, it is not necessary to clean other internal fields within the HAL
PPP handle during HAL_PPP_DeInit, as this clean-up is already performed in
HAL_PPP_Init (including the internal counters and pointers, internal variables and
callback pointers).
• Notes
o The HAL_PPP_DeInit function forces stopping any ongoing operation and
restores the state machine to their default/reset states. Therefore, this
function does not ASSERT on any state.
o The resources de-initialization (DMA, GPIO, NVIC, CLOCK) and the
peripheral reset (using RCC force/release reset) must be handled by the user
application, typically implemented in the mx_pppi_deinit()
STM32CubeMX2 generated function.
void HAL_PPP_DeInit(hal_ppp_handle_t *hppp)
{
/* Check the PPP handle allocation */
ASSERT_DBG_PARAM((hppp != NULL));
/* Check the PPP instance */
ASSERT_DBG_PARAM(IS_PPP_INSTANCE((PPP_TypeDef *) ((uint32_t)hppp->instance));
/* Stop current process/operation(s)s) */
(void) PPP_Disable(hppp);
/* or */
(void) PPP_Stop(hppp);
/* or */
(void) PPP_Abort(hppp);
/* or*/
Write needed registers/fields to stop any ongoing process
#if defined(USE_HAL_MUTEX) && (USE_HAL_MUTEX == 1)
/* Delete the PPP semaphore */
(void)HAL_OS_SemaphoreDelete(&hppp->semaphore);
69

#endif /* USE_PPP_MUTEX */
/* Reset the subinstances states when available */
hppp->{subinstance}_states[0] = HAL_PPP_{SUBINSTANCE}_STATE_RESET;
...
hppp->{subinstance}_states[#nb_subinstance] = HAL_PPP_{SUBINSTANCE}_STATE_RESET;
/* Or Reset the subinstance state unique when available */
hppp->{subinstance}_state = HAL_PPP_{SUBINSTANCE}_STATE_RESET;
/* Or Reset the processes states when available */
hppp->{process#i}_state = HAL_PPP_STATE_{PROCESS#i}_RESET;
...
hppp->{process#j}_state = HAL_PPP_STATE_{PROCESS#j}_RESET;
/* Reset the global state */
hppp->global_state = HAL_PPP_STATE_RESET;
}
11.1.3. HAL PPP instance retrieving
In some HAL drivers based on a handle, there could be some APIs that use directly the HAL
instance. these APIs are for security attributes setting or in case of HAL FLASH to provide
control APIs like (Ex: Unlock API or option bytes programming APIs).
To retrieve the HAL instance from the handle the following function must be provided:
hal_ppp_t HAL_PPP_GetInstance(const hal_ppp_handle_t *hppp)
{
ASSERT_DBG_PARAM((hppp != NULL));
ASSERT_DBG_PARAM(IS_PPP_ALL_INSTANCE((PPP_TypeDef *)((uint32_t)hppp->instance)));
return hppp->instance;
}
Additionally, for users that need to cohabitating HAL and LL drivers, the following functions
must be provided to retrieve the CMSIS/LL “PPP_TypeDef” instance
o Case of a handle-based driver (Ex: I2C, UART …): we retrieve the CMSIS/LL
“PPP_TypeDef” instance from the HAL PPP handle (hal_ppp_handle_t)
PPP_TypeDef *HAL_PPP_GetLLInstance(const hal_ppp_handle_t *hppp)
{
ASSERT_DBG_PARAM((hppp != NULL));
ASSERT_DBG_PARAM(IS_PPP_ALL_INSTANCE((PPP_TypeDef *)((uint32_t)hppp->instance)));
return ((PPP_TypeDef *)((uint32_t)((hppp)->instance)))
}
o Case of a driver not based on a handle (Ex HAL RAMCFG): we we retrieve the
CMSIS/LL “PPP_TypeDef” instance from the HAL PPP instance (hal_ppp_t)
PPP_TypeDef *HAL_PPP_GetLLInstance(hal_ppp_t instance)
{
ASSERT_DBG_PARAM(IS_PPP_ALL_INSTANCE((PPP_TypeDef *)((uint32_t)instance)));
70

return ((PPP_TypeDef *)((uint32_t)(instance))
}
11.2. Configuration APIs
11.2.1. HAL PPP global configuration
The global configuration APIs, HAL_PPP_SetConfig and HAL_PPP_GetConfig, must be
provided to apply or retrieve a configuration that is applicable for the entire peripheral
instance.
HAL_PPP_SetConfig Actions:
• Parameter Check: Use dedicated ASSERT_DBG_PARAM to check API parameters,
which can be enabled in debug mode using a dedicated compilation switch to reduce
footprint in the final release application.
• State Check: Ensure the global state is HAL_PPP_STATE_INIT or
HAL_PPP_STATE_IDLE using ASSERT_DBG_STATE, which can be enabled in
debug mode using a dedicated compilation switch to reduce footprint in the final
release application.
• Sub-instance State Check: When several sub-instances are available, use
ASSERT_DBG_STATE to check that the sub-instances are not in the ACTIVE state
(no sub-instance(s) running).
• Process State Check: When several process states are available, use
ASSERT_DBG_STATE to check that the processes are in the IDLE state (no process
running).
• Config Structure Pointer parameter Check: Verify that the config structure pointer is
not NULL (as it is a vital parameter and may lead to a hard fault if null) and return
HAL_INVALID_PARAM status in case of NULL. This check must be done under the
compilation switch USE_HAL_CHECK_PARAM to reduce footprint when the user
wants to bypass this check. Other parameters are checked by assert, including the
handle that was already checked during HAL_PPP_Init.
• Peripheral Disable: Disable the peripheral if mandatory to update the configuration
registers.
• Update Configuration Registers: Update the required peripheral configuration/control
registers according to the user configuration structure (using the appropriate LL
configuration APIs).
• Handle Update: Depending on the HAL PPP handle and implementation, update the
handle internal variable used by the process according to the user configuration if
needed.
• Peripheral Enable: Enable the peripheral once the configuration is applied if required
by the peripheral.
• Confirmation Flag Check: Depending on the peripheral, the configuration may require
waiting for a confirmation flag(s) (delayed configuration). In this case, a wait loop
should be used to confirm the configuration through the dedicated peripheral flag(s).
Use an intrinsic timeout define (HAL_PPP_FLAG_TIMEOUT), implemented in
stm32tnxx_hal_ppp.c with respect to the peripheral/product spec (not a public define).
When the dedicated flag(s) are confirmed, set the global state to
71

HAL_PPP_STATE_IDLE and return HAL_OK. If an error occurs during the global
configuration (a confirmation flag doesn’t rise), return HAL_ERROR.
• Immediate Configuration: When all the configuration registers take effect immediately
(no need to wait for a confirmation flag), set the global state to
HAL_PPP_STATE_IDLE at the end of the configuration and return HAL_OK.
Note: context with HAL2 versus HAL1, there are no more MspInit callbacks in HAL2
drivers. The equivalent Clock/GPIO/NVIC/DMA settings must be inserted before
HAL_PPP_Init or between HAL_PPP_Init and HAL_PPP_SetConfig without using a
dedicated MspInit Callback inside the generated the STM32CubeMX2 pppi_init().
hal_status_t HAL_PPP_SetConfig(hal_ppp_handle_t *hppp, const hal_ppp_config_t *p_config)
{
uint32_t tick_start; /* Only when need to wait on flag for a delayed configuration */
PPP_TypeDef *p_pppx;
/* Check the PPP handle and config allocation */
ASSERT_DBG_PARAM((hppp != NULL));
ASSERT_DBG_PARAM((p_config != NULL));
/* Check the parameters */
ASSERT_DBG_PARAM(IS_PPP_PARAMi(p_config->param_i));
/* Check the global state */
ASSERT_DBG_STATE(hppp->global_state, (uint32_t)HAL_PPP_STATE_INIT | (uint32_t)HAL_PPP_STATE_IDLE);
/* Check the Sub-Instance state when available */
/*case of multi subinstances variables */
ASSERT_DBG_STATE(hppp->{subinstance}_states[0],
(uint32_t)HAL_PPP_{SUBINSTANCE}_STATE_RESET |
(uint32_t)HAL_PPP_{SUBBLOCK#i}_{SUBINSTANCE}_STATE_ID
LE |
(uint32_t)HAL_PPP_{SUBBLOCK#j}_{SUBINSTANCE}_STATE_ID
LE);
...
ASSERT_DBG_STATE(hppp->{subinstance}_states[#nb_subinstance],
(uint32_t)HAL_PPP_{SUBINSTANCE}_STATE_RESET |
(uint32_t)HAL_PPP_{SUBBLOCK#i}_{SUBINSTAN
CE}_STATE_IDLE |
(uint32_t)HAL_PPP_{SUBBLOCK#j}_{SUBINSTAN
CE}_STATE_IDLE);
/* Or case of a single subinstance variable */
ASSERT_DBG_STATE(hppp-
>{subinstance}_state, (uint32_t)HAL_PPP_{SUBINSTANCE}_STATE_RESET |
(uint32_t)HAL_PPP_{SUBBLOCK#i}_{SUBINSTANCE}_STATE_IDLE
|
(uint32_t)HAL_PPP_{SUBBLOCK#j}_{SUBINSTANCE}_STATE_IDLE)
;
/* Or Check the Processes states when available */
ASSERT_DBG_STATE(hppp->{process#i}_state, HAL_PPP_STATE_{PROCESS}_IDLE);
#if defined(USE_HAL_CHECK_PARAM) && (USE_HAL_CHECK_PARAM == 1)
/* check the config struct pointer */
if(p_config == NULL)
{
return HAL_INVALID_PARAM;
}
#endif /* USE_HAL_CHECK_PARAM */
p_pppx = PPP_GET_INSTANCE(hppp);
72

/* Disable The PPP instance if mandatory by the peripheral to Update the configuration registers */
LL_PPP_Disable((p_pppx);
/* Call the LL to set the configuration items with adjustment if required */
LL_PPP_ConfigItem(p_pppx, #ADJ(conf->param_i, p_config->param_j));
...
LL_PPP_SetItem(p_pppx, #ADJ(p_config->param_k));
...
/* Enable the peripheral once the configuration applied if required by the peripheral */
LL_PPP_Enable(p_pppx);
/* if needed: Update the handle internal parameters according to the user config (with adjustment if
required) */
hppp->param_i = #ADJ(p_config->param_i);
...
//////////////// Case 1 //////////////////
/* When needed wait for a delayed configuration to be completed
(by checking PPP flag field)
*/
tick_start = HAL_GetTick();
do
{
if(LL_PPP_IsActiveFlag_BITNAME(p_pppx) == SET)
{
/* Update The HAL PPP global State */
hppp->global_state = HAL_PPP_STATE_IDLE;
return HAL_OK;
}
} while ((HAL_GetTick() - tick_start) <= HAL_PPP_FLAG_TIMEMOUT);
return HAL_ERROR;
//////////////// End of Case 1 ///////////
//////////////// Case 2 //////////////////
/* The configuration is immediate: no flags to be checked */
/* Update The HAL PPP global State */
hppp->global_state = HAL_PPP_STATE_IDLE;
return HAL_OK;
//////////////// End of Case 2 ///////////
}
Notes:
• Immediate Use: Depending on the peripheral, it can be used immediately after the
global configuration (e.g., UART).
• Sub-block Configuration: Some peripherals (e.g., TIM) require a global configuration
and may also require at least one channel configuration if used in output or input
compare mode.
The HAL_PPP_GetConfig API must retrieve the global configuration and must perform the
following actions:
• Check the API parameters using dedicated assertions that can be enabled in debug mode,
reducing the footprint in the final "release" application.
• Ensure that the global state is "IDLE" or "ACTIVE", meaning that a valid global
configuration has been applied.
• Read the required peripheral configuration/control registers using the corresponding LL
APIs and update the user configuration structure.
73

Note: Depending on the HAL PPP handle and implementation, the handle's internal variables
may also be used to update the configuration structure in addition to the peripheral registers.
void HAL_PPP_GetConfig(hal_ppp_handle_t *hppp, hal_ppp_config_t *p_config)
{
uint32_t config;
PPP_TypeDef *p_pppx;
/* Check the PPP handle & config allocation */
ASSERT_DBG_PARAM((hppp != NULL));
ASSERT_DBG_PARAM((p_config != NULL));
/* Check the global state */
ASSERT_DBG_STATE(hppp->global_state, (uint32_t)HAL_PPP_STATE_IDLE |
(uint32_t)HAL_PPP_STATE_ACTIVE);
/* Call the LL to Get the configuration items with
adjustment if required */
p_pppx = PPP_GET_INSTANCE(hppp);
config = LL_PPP_GetConfigItem(p_pppx, ...);
p_config->param_i = #ADJ_#i(config);
p_config->param_j = #ADJ_#j(config)
...
p_config->param_k = #ADJ_#k(p_pppx));
}
11.2.1. HAL PPP configuration reset
When the given PPP driver offers a valid functional configuration post-
reset, HAL_PPP_Reset[Feature]() or HAL_PPP_ResetConfig() must be provided to restore
the functional default configuration after a reset. These APIs must allow users to revert to the
default hardware configuration after applying a specific configuration
through HAL_PPP_SetConfig(). For example, the HAL_RCC_ResetSystemClock() service
restores the default system clock source.
The conditions to provide these API are:
• The PPP can be used immediately once clocked with a hardware reset configuration
that allows running a valid process.
• The reset configuration must be valid and functional regardless of the system
configuration.
• The peripheral must have no external dependencies. For example, after a reset, the
CRC peripheral allows running a CRC calculation with a default polynomial and
initialization value, independently of the system configuration.
When these conditions are met, the HAL_PPP_ResetConfig must be provided, and the HAL
PPP state machine does not need to provide a HAL_PPP_INIT_STATE. Instead,
the HAL_PPP_Init sets the state directly to IDLE. (Cf State machine)
void HAL_PPP_ResetConfig(hal_ppp_handle_t *hppp)
{
PPP_TypeDef *p_pppx;
/* Check the CRC handle allocation */
ASSERT_DBG_PARAM(hppp != NULL);
/* Check the global state */
ASSERT_DBG_STATE(hppp->global_state, HAL_PPP_STATE_IDLE);
/* Check the Sub-Instance state when available */
/*case of multi subinstances variables */
74

ASSERT_DBG_STATE(hppp->{subinstance}_states[0], (uint32_t)HAL_PPP_{SUBINSTANCE}_STATE_RESET |
(uint32_t)HAL_PPP_{SUBBLOCK#i}_{SUBINSTANCE}_STATE_IDLE |
(uint32_t)HAL_PPP_{SUBBLOCK#j}_{SUBINSTANCE}_STATE_IDLE);
...
ASSERT_DBG_STATE(hppp->{subinstance}_states[#nb_subinstance],
(uint32_t)HAL_PPP_{SUBINSTANCE}_STATE_RESET |
(uint32_t)HAL_PPP_{SUBBLOCK#i}_{SUBINSTANCE}_STATE_IDLE |
(uint32_t)HAL_PPP_{SUBBLOCK#j}_{SUBINSTANCE}_STATE_IDLE);
/* Or case of a single subinstance variable */
ASSERT_DBG_STATE(hppp->{subinstance}_state,
(uint32_t)HAL_PPP_{SUBINSTANCE}_STATE_RESET |
(uint32_t)HAL_PPP_{SUBBLOCK#i}_{SUBINSTANCE}_STATE_IDLE |
(uint32_t)HAL_PPP_{SUBBLOCK#j}_{SUBINSTANCE}_STATE_IDLE);
/* Or Check the Processes states when available */
ASSERT_DBG_STATE(hppp->{process#i}_state, HAL_PPP_STATE_{PROCESS}_IDLE);
p_pppx = PPP_GET_INSTANCE(hppp);
/* Reset the configuration items to their default/HW reset values */
/* either using config or unitary LL APIS */
LL_PPP_ConfigItem(p_pppx, param_i_reset_val, param_j_reset_val));
...
LL_PPP_SetItem(p_pppx, param_k_reset_val);
/* or using LL_WriteReg APIs when the config parameters are located in the same register */
LL_PPP_WriteReg(p_pppx, REG_X, REG_X_RESET_VAL);
}
11.2.2. HAL PPP sub-block configuration
The sub-block configuration APIs are used to configure a PPP sub-block. Depending on the
peripherals, a sub-block can be composed of or linked to several sub-instances. In such cases,
the "sub-instance" should be included in the sub-block configuration API naming and
parameters. For example, a TIMER output compare channel or an ADC channel. Two APIs,
HAL_PPP_{SUBBLOCK}_SetConfig{Subinstance} and
HAL_PPP_{SUBBLOCK}_GetConfig{Subinstance}, must be provided per sub-block to
apply and retrieve the sub-block configuration, respectively.
The HAL_PPP_{SUBBLOCK}_SetConfig{Subinstance} API must perform the following
actions:
• As with the global config API, check the API parameters using dedicated assertions
that can be enabled in debug mode, reducing the footprint in the final "release"
application.
• Ensure that the global state is HAL_PPP_STATE_IDLE (using dedicated assertions),
meaning that a global configuration has already been applied to proceed with the sub-
block and sub-instance configuration.
• Verify that the sub-instance is not in the "ACTIVE" state (using dedicated assertions).
• As with the global config API, check the config structure pointer against NULL and
return HAL_INVALID_PARAM status in case of NULL (other parameters are
checked only by assertions, including the handle that was already checked during the
HAL_PPP_Init).
• Update the required peripheral configuration/control registers according to the user
configuration structure (using the appropriate LL configuration APIs).
• Depending on the HAL PPP handle and implementation, update the handle's internal
variables used by the process according to the user configuration, if needed.
75

• Depending on the peripheral, the configuration may require waiting for a confirmation
flag(s) (delayed configuration). In this case, a wait loop must be used to confirm the
configuration through the dedicated peripheral flag(s). An intrinsic timeout define
(HAL_PPP_FLAG_TIMEOUT) must be used, implemented in the
stm32tnxx_hal_ppp.c file with respect to the peripheral/product specification (not a
public define). When the dedicated flag(s) are confirmed, the sub-instance state
changes to "IDLE" and the API returns HAL_OK. If an error occurs (a confirmation
flag doesn't rise), the API returns HAL_ERROR.
• When all the configuration registers of the given peripheral take effect immediately (no
need to wait for a confirmation flag), the sub-state changes to "IDLE" at the end of the
configuration, and the API returns HAL_OK.
hal_status_t HAL_PPP_{SUBBLOCK}_SetConfig{Subinstance}(hal_ppp_handle_t *hppp,
hal_ppp_{subinstance}_t {subinstance},
const hal_ppp_{subblock}_{subinstance}_config_t *p_config)
{
uint32_t tick_start; /*Only when need to wait on flag for a delayed configuration*/
PPP_TypeDef *p_pppx;
/* Check the PPP handle & config allocation */
ASSERT_DBG_PARAM((hppp != NULL));
ASSERT_DBG_PARAM((p_config != NULL));
/* Check the Subinstance */
ASSERT_DBG_PARAM(IS_PPP_{SUBBLOCK}_{SUBINSTANCE}(Subinstance));
/* Check the parameters */
ASSERT_DBG_PARAM(IS_PPP_{SUBBLOCK}_PARAMi(p_config->param_i));
/* Check the global state */
ASSERT_DBG_STATE(hppp->global_state , HAL_PPP_STATE_IDLE);
/* Check the Sub-Instance state */
/*case of multi subinstances variables */
ASSERT_DBG_STATE(hppp->{subinstance}_states[subinstance],
(uint32_t)HAL_PPP_{SUBINSTANCE}_STATE_RESET |
(uint32_t)HAL_PPP_{SUBBLOCK#i}_{SUBINSTANCE}_STATE_ID
LE |
(uint32_t)HAL_PPP_{SUBBLOCK#j}_{SUBINSTANCE}_STATE_ID
LE);
/*Or case of a single subinstance variable */
ASSERT_DBG_STATE(hppp-
>{subinstance}_state, (uint32_t)HAL_PPP_{SUBINSTANCE}_STATE_RESET |
(uint32_t)HAL_PPP_{SUBBLOCK#i}_{SUBINSTANCE}_STATE_IDL
E |
(uint32_t)HAL_PPP_{SUBBLOCK#j}_{SUBINSTANCE}_STATE_IDL
E);
#if defined(USE_HAL_CHECK_PARAM) && (USE_HAL_CHECK_PARAM ==1)
/* check the config struct pointer */
if(p_config == NULL)
{
return HAL_INVALID_PARAM;
}
#endif /* USE_HAL_CHECK_PARAM */
p_pppx = PPP_GET_INSTANCE(hppp);
/* Call the LL to set the {SUBBLOCK}/{Subinstance} configuration items with
adjustment if required
*/
LL_PPP_{SUBBLOCK}_ConfigItems(p_pppx, {Subinstance}, #ADJ(conf->param_i, p_config->param_j));
...
LL_PPP_{SUBBLOCK}_SetItem(p_pppx, {Subinstance}, #ADJ(p_config->param_k));
76

...
/* if needed: Update the handle internal parameters according to the user config
(with adjustment if required ) */
hppp->param_i = #ADJ(p_config->param_i);
...
//////////////// Case 1 //////////////////
/* When needed wait for a delayed configuration to be completed
(by checking PPP flag field)
*/
tick_start = HAL_GetTick();
do
{
if(LL_PPP_IsActiveFlag_BITNAME(p_pppx) == SET)
{
/* Update the subinstances states when available */
/*case of multi subinstances variables */
hppp->{subinstance}_states[Subinstance] = HAL_PPP_{SUBBLOCK#i}_{SUBINSTANCE}_STATE_IDLE;
/*Or case of a single subinstance variable */
hppp->{subinstance}_state = HAL_PPP_{SUBBLOCK#i}_{SUBINSTANCE}_STATE_IDLE;
return HAL_OK;
}
} while ((HAL_GetTick() - tick_start) <= HAL_PPP_FLAG_TIMEMOUT);
/* In case of Error */
return HAL_ERROR;
//////////////// End of Case 1 ///////////
//////////////// Case 2 //////////////////
/* The configuration is immediate: no flags to be checked */
/* Update the subinstances states when available */
/*case of multi subinstances variables */
hppp->{subinstance}_states[Subinstance] = HAL_PPP_{SUBBLOCK#i}_{SUBINSTANCE}_STATE_IDLE;
/*Or case of a single subinstance variable */
hppp->{subinstance}_state = HAL_PPP_{SUBBLOCK#i}_{SUBINSTANCE}_STATE_IDLE;
return HAL_OK;
//////////////// End of Case 2 ///////////
}
The HAL_PPP_{SUBBLOCK}_GetConfig{Subinstance} API must perform the following
actions:
• Check the API parameters using dedicated assertions that can be enabled in debug mode,
reducing the footprint in the final "release" application.
• Ensure that the global state is "IDLE" or above, meaning that a valid global configuration
has been applied (using dedicated assertions).
• Verify that the sub-instance state is not "RESET", indicating that a valid sub-instance
configuration has been applied (using assertions).
• Read the required peripheral configuration/control registers using the corresponding LL
APIs and update the user configuration structure.
Note: Depending on the HAL PPP handle and implementation, the handle's internal variables
may also be used to update the user configuration structure in addition to the peripheral
registers.
void HAL_PPP_{SUBBLOCK}_GetConfig{Subinstance}(hal_ppp_handle_t *hppp,
hal_ppp_{subinstance}_t Subinstance,
hal_ppp_{subblock}_{subinstance}_config_t *p_config)
77

{
uint32_t config;
PPP_TypeDef *p_pppx;
/* Check the PPP handle & config allocation */
ASSERT_DBG_PARAM((hppp != NULL));
ASSERT_DBG_PARAM((p_config != NULL));
/* Check the Subinstance */
ASSERT_DBG_PARAM(IS_PPP_{SUBBLOCK}_{SUBINSTANCE}(Subinstance));
/* Check the global state */
/* Check the Sub-Instance state */
/*case of multi subinstances variables */
/* Call the LL to Get the configuration items with adjustment if required */
p_pppx = PPP_GET_INSTANCE(hppp);
config = LL_PPP_{SUBBLOCK}_GetConfigItem((PPP_TypeDef *)((uint32_t)hppp->instance), ...);
p_config->param_i = #ADJ_#i(config);
p_config->param_j = #ADJ_#j(config)
...
p_config->param_k = #ADJ_#k(LL_PPP_{SUBBLOCK}_GetItem((PPP_TypeDef *)((uint32_t)hppp->instance)));
}
11.2.3. HAL PPP unitary configuration
The unitary configuration APIs allow configuring or retrieving a single item for a given
peripheral, such as setting the UART baud rate. Depending on the peripheral, the unitary item
can be applicable to the entire PPP instance, a specific sub-block, or a sub-instance of a sub-
block. These APIs are intended to dynamically modify or retrieve a unitary item, meaning that
a global or sub-block configuration has already been applied. Unitary configuration APIs must
first check if the corresponding state is "IDLE" (indicating that a global or sub-block
configuration has been applied) before modifying or retrieving an item.
For unitary items applicable to the entire PPP instance, two APIs per item must be
provided: HAL_PPP_SetItem and HAL_PPP_GetItem.
The HAL_PPP_SetItem API must perform the following actions:
• Check the API parameters using dedicated assertions that can be enabled in debug
mode, reducing the footprint in the final "release" application.
• Ensure that the global state is HAL_PPP_STATE_IDLE (using dedicated assertions),
meaning that a global configuration has already been applied.
• When several sub-instances are available, check that the sub-instances are not in the
"ACTIVE" state (using dedicated assertions, ensuring no sub-instance(s) are running).
• When several process states are available, check that the processes are in the "IDLE"
state (using dedicated assertions, ensuring no process is running).
• Update the required peripheral configuration/control registers according to the user
configuration item (using the appropriate LL configuration API).
• Depending on the HAL PPP handle and implementation, update the handle's internal
variables used by the process according to the user configuration.
• Depending on the peripheral, the configuration may require waiting for a confirmation
flag (delayed configuration). In this case, a wait loop must be used to confirm the
configuration through the dedicated peripheral flag. An intrinsic timeout define
(HAL_PPP_FLAG_TIMEOUT) must be used, implemented in
the stm32tnxx_hal_ppp.c file with respect to the peripheral/product specification (not a
public define). When the dedicated flag is confirmed,
the HAL_PPP_SetItem returns HAL_OK. If an error occurs during the item
configuration (a confirmation flag doesn’t rise), the API returns HAL_ERROR.
78

• When the item configuration registers take effect immediately (no need to wait for a
confirmation flag), the API returns HAL_OK immediately after setting the register
item.
The HAL_PPP_GetItem API must perform the following actions:
• Ensure that the global state is "IDLE" or "ACTIVE", meaning that a valid global
configuration has been applied.
• Check the API parameters using dedicated assertions that can be enabled in debug
mode, reducing the footprint in the final "release" application.
• Read the required peripheral configuration/control register using the corresponding LL
APIs and return the item value.
Examples:
hal_status_t HAL_TIM_SetCounterMode(const hal_tim_handle_t *htim,
hal_tim_counter_mode_t counter_mode);
hal_tim_counter_mode_t HAL_TIM_GetCounterMode(const hal_tim_handle_t *htim);
hal_status_t HAL_UART_SetBaudRate(const hal_uart_handle_t *huart, uint32_t baudrate);
uint32_t HAL_UART_GetBaudRate(const hal_uart_handle_t *huart);
For a unitary item that is applicable to a specific sub-block of the PPP instance, and when the
sub-block has several sub-instances, the unitary configuration APIs must reflect the sub-
instance in their naming and parameters.
Two APIs per item must be provided to handle sub-block unitary
configuration: HAL_PPP_{SUBBLOCK}_Set{Subinstance}Item and HAL_PPP_{SUBBLOCK
}_Get{Subinstance}Item. These APIs must respectively perform the same actions as
the HAL_PPP_SetItem/ HAL_PPP_GetItem, with the difference that the target register field to
be updated or read must be specific to the given sub-block and/or sub-instance.
Example:
hal_status_t HAL_TIM_IC_SetChannelSource(const hal_tim_handle_t *htim,
hal_tim_channel_t channel,
hal_tim_channel_src_t channel_src);
hal_tim_channel_src_t HAL_TIM_IC_GetChannelSource(const hal_tim_handle_t *htim,
hal_tim_channel_t channel);
11.2.1. Linking HAL DMA driver to HAL PPP driver
for each HAL driver that is supporting DMA based process, dedicated DMA link APIs must
be provided: One DMA link API per process with an explicit API naming.
Examples:
#if defined (USE_HAL_UART_DMA) && (USE_HAL_UART_DMA == 1)
/**
* @brief Set DMA channel for Transmission.
* @param huart Pointer to a \ref hal_uart_handle_t structure which contains the UART instance.
* @param hdma_tx Pointer to a hal_dma_handle_t structure which contains the DMA instance
* @retval HAL_OK The channel has been correctly set.
* @retval HAL_INVALID_PARAM hdma_tx is NULL.
*/
hal_status_t HAL_UART_SetTxDMA(hal_uart_handle_t *huart, hal_dma_handle_t *hdma_tx)
{
ASSERT_DBG_PARAM(huart != NULL);
ASSERT_DBG_PARAM(hdma_tx != NULL);
ASSERT_DBG_STATE(huart->global_state, HAL_UART_STATE_CONFIGURED);
ASSERT_DBG_STATE(huart->tx_state, (uint32_t)(HAL_UART_TX_STATE_IDLE | HAL_UART_TX_STATE_RESET));
#if defined(USE_HAL_CHECK_PARAM) && (USE_HAL_CHECK_PARAM == 1)
79

/* Check input parameter */
if (hdma_tx == NULL)
{
return HAL_INVALID_PARAM;
}
#endif /* USE_HAL_CHECK_PARAM */
huart->hdma_tx = hdma_tx;
hdma_tx->p_parent = huart;
return HAL_OK;
}
/**
* @brief Set DMA channel for Reception.
* @param huart Pointer to a \ref hal_uart_handle_t structure which contains the UART instance.
* @param hdma_rx Pointer to a hal_dma_handle_t structure which contains the DMA instance
* @retval HAL_OK The channel has been correctly set.
* @retval HAL_INVALID_PARAM hdma_rx is NULL.
*/
hal_status_t HAL_UART_SetRxDMA(hal_uart_handle_t *huart, hal_dma_handle_t *hdma_rx)
{
ASSERT_DBG_PARAM(huart != NULL);
ASSERT_DBG_PARAM(hdma_rx != NULL);
ASSERT_DBG_STATE(huart->global_state, HAL_UART_STATE_CONFIGURED);
ASSERT_DBG_STATE(huart->rx_state, (uint32_t)(HAL_UART_RX_STATE_IDLE | HAL_UART_RX_STATE_RESET));
#if defined(USE_HAL_CHECK_PARAM) && (USE_HAL_CHECK_PARAM == 1)
/* Check input parameter */
if (hdma_rx == NULL)
{
return HAL_INVALID_PARAM;
}
#endif /* USE_HAL_CHECK_PARAM */
huart->hdma_rx = hdma_rx;
hdma_rx->p_parent = huart;
return HAL_OK;
}
#endif /* USE_HAL_UART_DMA */
11.2.1. Setting and Getting user data
When a HAL PPP driver is built around a handle, it must allow the user to associate user data
with the given handle. An application should be able to store and retrieve a user data pointer
into and from the HAL PPP handle. Since the data type and format can vary from one
application to another, the user data pointer within the handle must be a pointer to void. The
HAL is not permitted to modify the user data; therefore, the pointer within the handle must be
a const void * pointer.
The HAL PPP driver must provide two APIs to set and get the user data pointer as follows:
#if defined (USE_HAL_PPP_USER_DATA) && (USE_HAL_PPP_USER_DATA == 1)
/**
* @brief Store User Data pointer into the handle.
* @param hppp Pointer to a hal_ppp_handle_t.
* @param p_user_data Pointer to the user data.
*/
void HAL_PPP_SetUserData(hal_ppp_handle_t *hppp, const void *p_user_data)
{
/* Check the PPP handle allocation */
ASSERT_DBG_PARAM((hppp != NULL));
80

hppp->p_user_data = p_user_data;
}
/**
* @brief Retrieve User Data pointer from the handle.
* @param hppp Pointer to a hal_ppp_handle_t.
* @retval Pointer to the user data.
*/
const void * HAL_PPP_GetUserData(const hal_ppp_handle_t *hppp)
{
/* Check the PPP handle allocation */
ASSERT_DBG_PARAM((hppp != NULL));
return (hppp->p_user_data);
}
#endif /* USE_HAL_PPP_USER_DATA == 1 */
Notes: The HAL must not perform any kind of treatment or checks on this user data pointer,
except initializing it to NULL in the HAL_PPP_Init. Thereafter, this pointer fully belongs to
the user. The HAL only stores it in the handle and then restores it to the user as is through the
appropriate HAL_PPP_SetUserData and HAL_PPP_GetUserData APIs.
11.3. HAL process and I/O operation APIs
The HAL processing APIs offer a set of functions designed to manage data processing for
various peripherals in a microcontroller. These APIs support three primary methods of data
processing: Polling, Interrupt (_IT), and Direct Memory Access (_DMA) referred as “_XX” in
the next code snippet. Additionally, for specific peripherals such as the FDCAN, a fourth
method may be available, which relies on user monitoring to determine the end of the process.
Note that only the polling process APIs (HAL_PPP_Process) takes a timeout parameter in
milliseconds (timeout_ms)
In all these methods, the following initial steps are required:
1. Check all parameters validity (handle included) using asserts.
hal_status_t HAL_PPP_Process_XX(hal_ppp_handle_t *hppp, const void *p_data, uint32_t size_byte, ...)
{
ASSERT_DBG_PARAM(hppp != NULL);
ASSERT_DBG_PARAM(p_data != NULL);
ASSERT_DBG_PARAM(size_byte != 0);
...
}
2. Check the state(s) validity to proceed with the requested process using asserts.
hal_status_t HAL_PPP_Process_XX(hal_ppp_handle_t *hppp, const void *p_data,
uint32_t size_byte, ...)
{
...
/* Check the global state must be IDLE or CONFIGURED depending of the implemlenation */
ASSERT_DBG_STATE(hppp->global_state, HAL_PPP_STATE_IDLE);
/* Check the Processe state when available/applicable */
ASSERT_DBG_STATE(hppp->process#i_state, HAL_PPP_PROCESS#i_STATE_IDLE);
...
}
81

3. Check the vital parameters under the compilation switch
USE_HAL_CHECK_PARAM
hal_status_t HAL_PPP_Process_XX(hal_ppp_handle_t *hppp, const void *p_data, uint32_t size_byte,
uint32_t timeout_ms)
{
...
#if defined(USE_HAL_CHECK_PARAM) && (USE_HAL_CHECK_PARAM == 1)
/* Check input parameters */
if ((p_data == NULL) || (size_byte == 0U))
{
return HAL_INVALID_PARAM;
}
#endif /* USE_HAL_CHECK_PARAM */
...
}
4. Convert the instance stored into the handle to the physical instance as per the CMSIS
device (note that a dedicated private PPP_GET_INSTANCE macro must be provided
to allow this action for the various functions provided by the given HAL PPP driver
#define PPP_GET_INSTANCE (handle) ((PPP_TypeDef *)((uint32_t)(handle)->instance))
...
hal_status_t HAL_PPP_Process_XXX(hal_ppp_handle_t *hppp, const void *p_data,
uint32_t size_byte, uint32_t timeout_ms)
{
...
PPP_TypeDef *p_pppx;
p_pppx = PPP_GET_INSTANCE(handle);
...
}
5. Move the state from the initial required state (usually IDLE state) to the corresponding
state of the given process using the macro HAL_CHECK_UPDATE_STATE
/* in case of a global state machine only (no dedicated state machine per process) */
HAL_CHECK_UPDATE_STATE(hppp, hppp->global_state, HAL_PPP_STATE_IDLE, HAL_PPP_STATE_ACTIVE);
/* in case of a dedicated state machine per process */
HAL_CHECK_UPDATE_STATE(hppp, process#i_state, , HAL_PPP_PROCESS#i_STATE_IDLE,
HAL_PPP_PROCESS#i_STATE_ACTIVE);
6. Reset the error code variable within the handle under the compilation switch
USE_HAL_PPP_GET_LAST_ERRORS
/* case of one single variable to hold the last error codes within the handle */
#if defined (USE_HAL_PPP_GET_LAST_ERRORS) && (USE_HAL_PPP_GET_LAST_ERRORS == 1)
hppp->last_error_codes = 0;
#endif /* USE_HAL_PPP_GET_LAST_ERRORS */
/* case of a variable to hold the last error codes per process within the handle */
#if defined (USE_HAL_PPP_GET_LAST_ERRORS) && (USE_HAL_PPP_GET_LAST_ERRORS == 1)
hppp->last_process#i_error_codes = 0;
#endif /* USE_HAL_PPP_GET_LAST_ERRORS */
82

11.3.1. Polling/blocking model
The Polling APIs in the Hardware Abstraction Layer (HAL) are designed to manage
peripheral operations using a blocking approach. These APIs typically follow a standard
naming convention, such as HAL_PPP_Process, where PPP represents the specific peripheral
(e.g., UART, I2C, SPI) and Process denotes the I/O operation (e.g., Transmit, Receive,
Encrypt, Decrypt). The HAL_PPP_Process function continuously checks the status of the
peripheral until the desired condition is met, such as the completion of a data transmission or
reception. During this period, the CPU remains engaged in polling the peripheral's status
registers, ensuring that the operation is fully completed before proceeding. This approach is
straightforward and easy to implement, making it suitable for simple applications where the
CPU can afford to wait. However, it can lead to inefficient use of CPU resources, as the CPU
is unable to perform other tasks while polling. Despite this drawback, the Polling APIs provide
a reliable method for managing peripheral operations in scenarios where precise timing and
multitasking are not critical.
After applying the required initial steps (1 to 6), the polling processes sequence must be
implemented as follows:
7. Once the various checks are completed and the state is transitioned to the required one
according to the given process, the necessary registers and fields should be populated
to initiate the process.
8. Enter a loop to continuously manage the data feeding into the peripheral or retrieving
data from the peripheral. This involves:
o Waiting for the relevant flags to indicate that the data is ready to be written to
or read from the peripheral.
o Ensuring that the data transfer is handled efficiently and accurately,
maintaining the integrity of the process.
o Within this loop, perform the following additional tasks:
▪ Error Checking: Accumulate errors within the appropriate handle field
under the compilation switch USE_HAL_PPP_GET_LAST_ERRORS.
▪ Timeout Monitoring: Monitor the elapsed time and compare it to the
user-given timeout.
9. The loop must end under the following conditions:
o Completion: All data are processed within the given user timeout.
o Blocking Error: A blocking error occurs, making it impossible to continue the
process.
o Timeout: The operation exceeds the given user timeout.
10. When the processing loop ends, perform the following actions:
o Populate the necessary registers and fields to end the process properly.
o Move the state back to the initial required state (usually the
HAL_PPP_STATE_IDLE state) by directly setting the appropriate handle state
field.
o Return the appropriate status code:
▪ HAL_OK if the process ended successfully.
▪ HAL_ERROR if an error occurred.
83

▪ HAL_TIMEOUT if the process couldn't be finalized within the user-
given timeout.
84

85

11.3.2. Interrupt asynchronous model
The Interrupt (_IT) model in the HAL leverages hardware interrupts to manage peripheral
operations efficiently. In this model, the HAL_PPP_Process_IT API initiates a peripheral
operation, arms the required interrupts at the peripheral level to ensure data processing, and
then returns control to the caller, allowing the CPU to proceed with other tasks. When the
peripheral completes the operation or reaches a specified condition (such as an input ready
interrupt or output data available interrupt), it generates an interrupt signal to notify the CPU.
The CPU then temporarily halts its current tasks to execute an interrupt service routine (ISR)
that calls the appropriate HAL_PPP_IRQHandler to handle the peripheral's data processing.
This approach allows for more efficient use of CPU resources, as the CPU can perform other
operations while waiting for the interrupt, making it ideal for applications that require
multitasking and timely responses. The “_IT” model is particularly beneficial in scenarios
where precise timing and efficient CPU utilization are critical.
In the “IT” model, it is forbidden to use blocking statements that depend on the HAL Time
Base (IT dependency). Instead, any necessary blocking statements, such as filling or dumping
FIFOs, must be managed in a tickless mode, utilizing CPU cycle counting. This restriction
ensures that “IT” processes can be safely called within an ISR or a callback without causing
conflicts or dependencies on the system tick.
After applying the required initial steps (1 to 6), The HAL_PPP_Process_IT sequence must be
implemented as follows:
7. Once the various checks are completed and the state is transitioned to the required one
according to the given process, the HAL_PPP_Process_IT function must:
o Store the data buffer and size into the corresponding handle pointer parameters.
o Initialize a counter within the handle that will decrement as data processing
progresses, managed by the HAL_PPP_IRQHandler when the corresponding
interrupts are triggered.
hal_status_t HAL_PPP_Process_IT(hal_ppp_handle_t *hppp, const void *p_data, uint32_t
size_byte)
{
...
hppp->p_buff = p_data;
hppp->xfer_size = size_byte;
hppp->xfer_count = size_byte;
...
}
8. Populate the necessary registers and fields to initiate the process. Depending on the
peripheral, this may include writing an initial amount of data from the given data
buffer into the peripheral register to start the process.
9. Activate the required interrupts to handle data processing, control, and error catching.
11. In In case the "IT" process did not start successfully due to an internal peripheral error
signaled by a specific flag, perform the following actions:
o Populate the necessary registers and fields to end the process properly
(including interrupts deactivation and various flags clearing).
86

o Move the state back to the initial required state (usually the IDLE state) by
directly setting the appropriate handle state field.
o Return HAL_ERROR.
12. In case the "IT" process starts successfully, return HAL_OK and leave the data
processing to be handled by the HAL_PPP_IRQHandler, which will ensure the
following:
o Data and Control Processing: Handle data and control processing upon
receiving the corresponding interrupts.
o Error Management: Manage errors upon receiving the corresponding error
interrupts.
o Process Completion: Handle process completion upon the corresponding
process complete interrupt or blocking error interrupts.
o Populate the necessary registers and fields to end the process properly,
including deactivating interrupts and clearing various flags.
o Update the state back to the initial required state (usually the
HAL_PPP_STATE_IDLE state) by directly setting the appropriate
handle state field.
o Call the corresponding callback to inform the user about the end of
the process, whether it ended successfully or with an error.
87

88

11.3.3. DMA asynchronous model
The Direct Memory Access (DMA) model in the HAL leverages general purpose DMA
controllers to manage peripheral operations efficiently, offloading data transfer tasks from the
CPU. Before calling HAL_PPP_Process_DMA, the user must first link the given HAL DMA
handle to the HAL PPP handle using the appropriate API (e.g., HAL_UART_SetTxDMA).
The HAL_PPP_Process_DMA API must initiate the peripheral operation then start a DMA to
handle data transfers between memory and the peripheral, or vice versa. The API then returns
control to the caller, allowing the CPU to proceed with other tasks.
The HAL DMA callbacks (half transfer, transfer complete, transfer error) must be set by
the HAL_PPP_Process_DMA to internal PPP functions that handle these events. These
internal functions ensure the process is properly completed and report the completion to the
user through the various HAL PPP callbacks. This means that the HAL DMA callbacks are
not user callbacks in this context but are intercepted by the HAL PPP itself. Essentially, the
DMA acts as a service peripheral for the PPP peripheral.
The DMA controller autonomously handles the data transfer, generating interrupts to notify
the CPU upon completion or when specific conditions are met, such as transfer complete or
transfer error. The CPU temporarily halts its current tasks to execute the corresponding DMA
channel interrupt service routine (ISR) that calls the appropriate HAL_DMA_IRQHandler to
manage the completion of the data processing. The HAL_DMA_IRQHandler will trigger the
various DMA callbacks that are set to internal HAL PPP callbacks, as explained above.
This approach allows for highly efficient use of CPU resources, as the CPU can perform other
operations while the DMA controller manages data transfers in the background. The DMA
model is particularly advantageous in scenarios where large amounts of data need to be
transferred quickly and efficiently, and where minimizing CPU involvement is critical.
Same as “IT” model, in the DMA model, it is forbidden to use blocking statements that
depend on the HAL Time Base (IT dependency). Instead, any necessary blocking statements,
such as filling or dumping FIFOs, must be managed in a tickless mode, utilizing CPU cycle
counting. This restriction ensures that DMA processes can be safely called within an ISR or
callbacks without causing conflicts or dependencies on the system tick.
The HAL_PPP_Process_DMA must apply the same required initial steps (1 to 6) with a
particular emphasis on step 3. Specifically, the DMA handle corresponding to the given
process is considered a vital parameter that must not be null and thus must be checked under
the USE_HAL_CHECK_PARAM compilation flag. Concretely, this means that a DMA
handle must have been properly linked to the PPP handle prior to running the given process.
hal_status_t HAL_PPP_Process_DMA/_Opt(hal_ppp_handle_t *hppp, const void *p_data, uint32_t size_byte)
{
...
#if defined(USE_HAL_CHECK_PARAM) && (USE_HAL_CHECK_PARAM == 1)
/* Check input parameters */
if ((p_data == NULL) || (size_byte == 0U) || (hppp->hdma_#i == NULL))
{
89

return HAL_INVALID_PARAM;
}
#endif /* USE_HAL_CHECK_PARAM */
...
}
After applying the required initial steps (1 to 6), The HAL_PPP_Process_DMA sequence must
be implemented as follows:
7. Once the various checks are completed and the state is transitioned to the required one
according to the given process, the HAL_PPP_Process_DMA function must:
o Store the data buffer and size into the corresponding handle pointer parameters.
hal_status_t HAL_PPP_Process_DMA(hal_ppp_handle_t *hppp, const void *p_data, uint32_t size_byte)
{
...
hppp->p_buff = p_data;
hppp->xfer_size = size_byte;
hppp->xfer_count = size_byte;
...
}
8. Set the DMA callbacks to the dedicated internal PPP functions that will intercept these
DMA events
hal_status_t HAL_PPP_Process_DMA(hal_ppp_handle_t *hppp, const void *p_data, uint32_t size_byte)
{
...
/* Set the PPP DMA transfer complete callback */
hppp->hdma_#i->p_xfer_cplt_cb = PPP_DMAProcessCplt;
/* Set the PPP DMA Half transfer complete callback */
hppp->hdma_#i->p_xfer_halfcplt_cb = PPP_DMAProcessHalfCplt;
/* Set the DMA error callback */
hppp->hdma_#i->p_xfer_error_cb = PPP_DMAError;
...
}
9. Start the DMA transfer by calling the HAL_DMA_StartPeriphXfer_IT_Opt function.
Set the source and destination parameters to the user input buffer and the peripheral
data register, respectively, based on the transfer direction (read or write). The last
parameter of this function allows control over optional DMA interrupts (e.g., half
transfer). Typically, this parameter is set to HAL_DMA_OPT_IT_DEFAULT, which
enables the default set of DMA interrupts. If the PPP process does not require optional
DMA interrupts, such as the half transfer interrupt, you can set this parameter to
HAL_DMA_OPT_IT_NONE.
In case the DMA transfer did not start successfully, perform the following actions:
o Set the last error code field into the handle to indicate a DMA error.
o Move the state back to the initial required state (usually the
HAL_PPP_STATE_IDLE state) by directly setting the appropriate handle state
field.
o Return HAL_ERROR.
90

hal_status_t HAL_PPP_Process_DMA(hal_ppp_handle_t *hppp, const void *p_data, uint32_t size_byte)
{
...
if (HAL_DMA_StartPeriphXfer_IT_Opt(hppp->hdma_#i, (uint32_t)&p_ppp->DR,
(uint32_t)hppp->p_buff, size, HAL_DMA_OPT_IT_DEFAULT) != HAL_OK)
{
#if defined (USE_HAL_PPP_GET_LAST_ERRORS) && (USE_HAL_PPP_GET_LAST_ERRORS == 1)
huart->last_{process#i}_error_codes |= HAL_PPP_{PROCESS#i}_ERROR_DMA;
#endif /* USE_HAL_UART_GET_LAST_ERRORS */
hppp->{process#i}_state = HAL_PPP_{PROCESS#i}_STATE_IDLE;
return HAL_ERROR;
}
...
}
10. Populate the necessary registers and fields to initiate the process. Depending on the
peripheral, this may include activating specific control PPP interrupts. These interrupts
will be intercepted by the HAL_PPP_IRQHandler itself. Note that even in a DMA
model, certain interrupts may be necessary to control the process at the PPP level.
11. Enable the DMA request from the peripheral to the DMA by writing to the appropriate
register field using the dedicated LL API. Note that, depending on the peripheral, after
enabling the DMA request at the PPP level, you may need to explicitly enable the PPP
by writing to the appropriate register field using the corresponding LL API.
12. If the DMA process starts successfully, return HAL_OK and leave the data processing
to be handled as follows:
o DMA Handling: The DMA itself will manage the data transfer and signal
various steps, such as half transfer, transfer complete, or errors, to the HAL
PPP driver through the appropriate callbacks.
o PPP Interrupt Handling: The HAL_PPP_IRQHandler will manage control and
error handling, if any.
13. Process Completion Signaled by the DMA: The process completion is indicated by the
corresponding DMA callback (transfer complete or error callbacks) that are set by the
HAL PPP itself. Upon process completion, the implementation of the
PPP_DMAProcessCplt and PPP_DMAError callbacks must take care of the following
actions:
o Populate the necessary PPP registers and fields to properly end the process,
including deactivating interrupts (if any) and clearing various flags.
o Disable the DMA requests from the PPP to the DMA.
o Update the PPP state back to the initial required state (usually the IDLE state)
by directly setting the appropriate HAL PPP handle state field.
o Call the corresponding HAL PPP callback to inform the user about the end of
the process, whether it ended successfully or with an error.
14. Process Completion Signaled by a PPP Error Interrupt: In case the peripheral provides
error management, the HAL_PPP_IRQHandler must act as follows when a blocking
error interrupt occurs:
91

o Store the error code to the corresponding HAL PPP handle field
o Disable the DMA requests from the PPP to the DMA.
o Set the DMA abort callback to a dedicated internal PPP function that will
intercept the DMA abort event and end the process properly, including:
o Populate the necessary PPP registers and fields to end the process
properly, deactivate interrupts (if any), and clear various flags.
o Update the state back to the initial required state (usually the IDLE
state) by directly setting the appropriate handle state field.
o Call the corresponding HAL PPP error callback to inform the user.
11.3.4. Aborting an asynchronous process
The HAL_PPP_Abort and HAL_PPP_Abort_IT functions must be provided to abort any
ongoing asynchronous process, including interrupt (IT) and DMA processes.
For a given PPP instance. HAL_PPP_Abort must be a synchronous, blocking function that
stops the current data transfer, disables the peripheral, clears any error flags, and put the
handle state back to “IDLE” state. .
Conversely, HAL_PPP_Abort_IT must be an asynchronous, non-blocking function that
initiates the abort of an ongoing asynchronous process and returns immediately, allowing the
application to continue executing other tasks. The actual stopping of the data transfer and
resetting of the handle state must be handled by the interrupt service routine (ISR) associated
to the ongoing asynchronous process , which must call a dedicated callback to signal the
completion of the abort process. This function must be suitable for scenarios where the abort
process can be handled in the background without blocking the main application flow.
11.3.5. Asynchronous model, filtering optional interrupts
The conventional HAL PPP asynchronous processes (IT and DMA) usually enable all the
interrupts related to the given process. Some of these interrupts are mandatory (e.g., Transfer
Complete), while others are informative and not mandatory for the HAL process (e.g., Half
Transfer). In addition to these conventional asynchronous processes, the HAL must provide
users with ways to filter the optional interrupts. For analog peripherals (ADC, DAC, and
TIM), a silent asynchronous mode must also be provided: a non-blocking mode with DMA in
circular mode and without interrupt signaling.
To address these needs, the HAL must provide additional IT and DMA process APIs with an
"_Opt" postfix: HAL_PPP_Process_IT_Opt and HAL_PPP_Process_DMA_Opt, with the
following rules:
• API Prototypes:
o These APIs must have the same prototype as the original process APIs but with
an additional uint32_t interrupts parameter that indicates the optional interrupts
to be enabled.
o This interrupts parameter can be a combination of several optional interrupts.
o Dedicated defines must be provided to be used for the interrupts parameter.
• Defines for Optional Interrupts:
92

o Clear All Optional Interrupts: One define to clear all the optional interrupts:
HAL_PPP_OPT_NONE (must be the numerical value zero).
o DMA Silent Mode: One define to select the DMA silent mode:
HAL_PPP_OPT_DMA_SILENT (i.e., the DMA asynchronous process will not
issue any DMA interrupt).
o Optional Interrupt Defines: Defines must be provided for each process (IT and
DMA) per interrupt:
▪ HAL_PPP_OPT_DMA_{PROCESS#i}_IT_{interrupt_name}
▪ HAL_PPP_OPT_IT_{PROCESS#i}_IT_{interrupt_name}
• Behavior Based on interrupts Parameter:
o When the interrupts parameter is set to HAL_PPP_OPT_NONE, all the
optional interrupts must be disabled for the given process.
o When the interrupts parameter is set to HAL_PPP_OPT_DMA_SILENT, the
DMA-based process must be in DMA silent mode, i.e., the DMA used by the
given peripheral will not issue interrupts.
o When the interrupts parameter is set to
HAL_PPP_OPT_IT_{PROCESS#i}_DEFAULT or
HAL_PPP_OPT_DMA_{PROCESS#i}_DEFAULT, the
HAL_PPP_Process_IT_Opt or HAL_PPP_Process_DMA_Opt APIs must
respectively behave the same as the conventional HAL_PPP_Process_IT or
HAL_PPP_Process_DMA.
• DMA Driver API: The DMA driver must provide a HAL_DMA_StartPeriphXfer_Opt
API with the parameter interrupts allowing to filter optional interrupts or start the
DMA in silent mode, i.e., without any enabled interrupt. This is to be used by the HAL
PPP driver to implement the HAL_PPP_Process_DMA_Opt APIs.
Examples:
• Optional defines:
/** UART_Optional_Interrupts UART Optional Interrupts */
/** UART_Transmit_IT_Optional_Interrupts UART Optional Interrupts for Transmit interrupt process */
/*! Do not activate optional interruptions on TX IT process */
#define HAL_UART_OPT_TX_IT_NONE 0U
/*! Activate FIFO Empty optional interruption */
#define HAL_UART_OPT_TX_IT_FIFO_EMPTY (1U << 30U)
/*! Activate Clear To Send optional interruption */
#define HAL_UART_OPT_TX_IT_CLEAR_TO_SEND (1U << 29U)
/*! Activate FIFO Empty and Clear To Send optional interruptions */
#define HAL_UART_OPT_TX_IT_DEFAULT (HAL_UART_OPT_TX_IT_FIFO_EMPTY |
HAL_UART_OPT_TX_IT_CLEAR_TO_SEND)
#if defined (USE_HAL_UART_DMA) && (USE_HAL_UART_DMA == 1U)
/* UART_Transmit_DMA_Optional_Interrupts UART Optional Interrupts for Transmit DMA process */
/*! Do not activate optional interruptions on TX DMA process */
#define HAL_UART_OPT_DMA_TX_IT_NONE 0U
/*! Activate DMA Half Transfer optional interruption */
#define HAL_UART_OPT_DMA_TX_IT_HT (HAL_DMA_OPT_IT_HT)
/*! Activate DMA Half Transfer optional interruption */
#define HAL_UART_OPT_DMA_TX_IT_DEFAULT (HAL_UART_OPT_DMA_TX_IT_HT)
#if defined(USE_HAL_DMA_LINKEDLIST) && (USE_HAL_DMA_LINKEDLIST == 1)
93

/*! Activate Silent Mode on DMA */
#define HAL_UART_OPT_DMA_TX_IT_SILENT (HAL_DMA_OPT_IT_SILENT)
#endif /* USE_HAL_DMA_LINKEDLIST */
• IT based process: To avoid duplicating code between
the HAL_PPP_Process_IT and HAL_PPP_Process_IT_Opt APIs, it is recommended to
provide a private function that implements the process, taking the optional interrupts
parameter. In this case, the public functions must perform the necessary parameter and
state checks, and then call the private function to proceed with the process.
static hal_status_t UART_Start_Transmit_IT(hal_uart_handle_t *huart, const uint8_t *p_data, uint32_t
size,
uint32_t interrupts);
hal_status_t HAL_UART_Transmit_IT(hal_uart_handle_t *huart, const void *p_data, uint32_t size_byte)
{
ASSERT_DBG_PARAM(huart != NULL);
...
ASSERT_DBG_STATE(huart->global_state, HAL_UART_STATE_CONFIGURED);
ASSERT_DBG_STATE(huart->tx_state, HAL_UART_TX_STATE_IDLE);
#if defined(USE_HAL_CHECK_PARAM) && (USE_HAL_CHECK_PARAM == 1)
/* Check input parameters */
if ((p_data == NULL) || (size_byte == 0U))
{
return HAL_INVALID_PARAM;
}
#endif /* USE_HAL_CHECK_PARAM */
HAL_CHECK_UPDATE_STATE(huart, tx_state, HAL_UART_TX_STATE_IDLE, HAL_UART_TX_STATE_ACTIVE);
return UART_Start_Transmit_IT(huart, (const uint8_t *)p_data, size_byte, HAL_UART_OPT_TX_IT_NONE);
}
hal_status_t HAL_UART_Transmit_IT_Opt(hal_uart_handle_t *huart, const void *p_data, uint32_t size_byte,
uint32_t interrupts)
{
ASSERT_DBG_PARAM(huart != NULL);
...
ASSERT_DBG_PARAM(IS_UART_OPT_TX_IT(interrupts));
ASSERT_DBG_STATE(huart->global_state, HAL_UART_STATE_CONFIGURED);
ASSERT_DBG_STATE(huart->tx_state, HAL_UART_TX_STATE_IDLE);
#if defined(USE_HAL_CHECK_PARAM) && (USE_HAL_CHECK_PARAM == 1)
/* Check input parameters */
if ((p_data == NULL) || (size_byte == 0U))
{
return HAL_INVALID_PARAM;
}
#endif /* USE_HAL_CHECK_PARAM */
HAL_CHECK_UPDATE_STATE(huart, tx_state, HAL_UART_TX_STATE_IDLE, HAL_UART_TX_STATE_ACTIVE);
return UART_Start_Transmit_IT(huart, (const uint8_t *)p_data, size_byte, interrupts);
}
hal_status_t UART_Start_Transmit_IT(hal_uart_handle_t *huart, const uint8_t *p_data, uint32_t size,
uint32_t interrupts)
{
...
/* enable the optional interrupts when selected */
if ((interrupts & HAL_UART_OPT_TX_IT_FIFO_EMPTY) == HAL_UART_OPT_TX_IT_FIFO_EMPTY)
94

{
LL_USART_EnableIT_TXFE(p_uartx);
}
if ((interrupts & HAL_UART_OPT_TX_IT_CLEAR_TO_SEND) == HAL_UART_OPT_TX_IT_CLEAR_TO_SEND)
{
LL_USART_EnableIT_CTS(p_uartx);
}
...
return HAL_OK;
}
• DMA based process:
o To avoid duplicating code between the HAL_PPP_Process_DMA and
HAL_PPP_Process_DMA_Opt APIs, it is recommended to provide a private
function that implements the process, taking the optional interrupts parameter.
o Private Function Implementation: Create a private function that handles the
DMA process, accepting an optional interrupts parameter. This private function
should mask the given interrupts with those related to the PPP peripheral and
activate the enabled ones. It should then call the
HAL_PPP_Process_DMA_Opt function with the last parameter being the
interrupts masked with the DMA-specific optional interrupts.
o Public Functions: The public functions HAL_PPP_Process_DMA and
HAL_PPP_Process_DMA_Opt should perform the necessary parameter and
state checks. After the checks, they should call the private function to proceed
with the process.
o By following this approach, code duplication is minimized, and the
implementation becomes more maintainable and efficient.
static hal_status_t UART_Start_Transmit_DMA(hal_uart_handle_t *huart, const uint8_t *p_data, uint32_t
size,
uint32_t interrupts);
hal_status_t HAL_UART_Transmit_DMA(hal_uart_handle_t *huart, const void *p_data, uint32_t size_byte)
{
ASSERT_DBG_PARAM(huart != NULL);
...
ASSERT_DBG_STATE(huart->global_state, HAL_UART_STATE_CONFIGURED);
ASSERT_DBG_STATE(huart->tx_state, HAL_UART_TX_STATE_IDLE);
#if defined(USE_HAL_CHECK_PARAM) && (USE_HAL_CHECK_PARAM == 1)
/* Check input parameters */
if ((p_data == NULL) || (size_byte == 0U))
{
return HAL_INVALID_PARAM;
}
#endif /* USE_HAL_CHECK_PARAM */
HAL_CHECK_UPDATE_STATE(huart, tx_state, HAL_UART_TX_STATE_IDLE, HAL_UART_TX_STATE_ACTIVE);
return UART_Start_Transmit_DMA(huart, (const uint8_t *)p_data,
size_byte, HAL_UART_OPT_DMA_TX_IT_HT);
}
hal_status_t HAL_UART_Transmit_DMA_Opt(hal_uart_handle_t *huart, const void *p_data, uint32_t
size_byte,
uint32_t interrupts)
95

{
ASSERT_DBG_PARAM(huart != NULL);
...
ASSERT_DBG_PARAM(IS_UART_OPT_TX_DMA(interrupts));
#if defined(USE_HAL_DMA_LINKEDLIST) && (USE_HAL_DMA_LINKEDLIST == 1)
ASSERT_DBG_PARAM(IS_UART_DMA_TX_VALID_SILENT_MODE(huart->hdma_tx, interrupts));
#endif /* USE_HAL_DMA_LINKEDLIST */
ASSERT_DBG_STATE(huart->global_state, HAL_UART_STATE_CONFIGURED);
ASSERT_DBG_STATE(huart->tx_state, HAL_UART_TX_STATE_IDLE);
#if defined(USE_HAL_CHECK_PARAM) && (USE_HAL_CHECK_PARAM == 1)
/* Check input parameters */
if ((p_data == NULL) || (size_byte == 0U))
{
return HAL_INVALID_PARAM;
}
#endif /* USE_HAL_CHECK_PARAM */
HAL_CHECK_UPDATE_STATE(huart, tx_state, HAL_UART_TX_STATE_IDLE, HAL_UART_TX_STATE_ACTIVE);
return UART_Start_Transmit_DMA(huart, (const uint8_t *)p_data, size_byte, interrupts);
}
hal_status_t UART_Start_Transmit_DMA(hal_uart_handle_t *huart, const uint8_t *p_data, uint32_t size,
uint32_t interrupts)
{
uint32_t interrupts_dma;
...
#if defined(USE_HAL_DMA_LINKEDLIST) && (USE_HAL_DMA_LINKEDLIST == 1)
if (interrupts == HAL_UART_OPT_DMA_TX_IT_SILENT)
{
interrupts_dma = HAL_UART_OPT_DMA_TX_IT_SILENT;
}
else
#endif /* USE_HAL_DMA_LINKEDLIST */
{
interrupts_dma = (interrupts & HAL_UART_OPT_DMA_TX_IT_HT);
}
...
if (HAL_DMA_StartPeriphXfer_IT_Opt(huart->hdma_tx, (uint32_t)huart->p_tx_buff, (uint32_t)&p_uartx-
>TDR,
size, interrupts_dma) != HAL_OK)
{
huart->tx_state = HAL_UART_TX_STATE_IDLE;
#if defined (USE_HAL_UART_GET_LAST_ERRORS) && (USE_HAL_UART_GET_LAST_ERRORS == 1)
huart->last_transmission_error_codes |= HAL_UART_TRANSMIT_ERROR_DMA;
#endif /* USE_HAL_UART_GET_LAST_ERRORS */
return HAL_ERROR;
}
}
...
if (((interrupts & HAL_UART_OPT_TX_IT_CLEAR_TO_SEND) == HAL_UART_OPT_TX_IT_CLEAR_TO_SEND)
#if defined(USE_HAL_DMA_LINKEDLIST) && (USE_HAL_DMA_LINKEDLIST == 1)
&& (interrupts_dma != HAL_UART_OPT_DMA_TX_IT_SILENT)
#endif /* USE_HAL_DMA_LINKEDLIST */
)
{
LL_USART_EnableIT_CTS(p_uartx);
}
return HAL_OK;
}
96

11.3.6. Monitoring model
For some peripherals, data processing can be fully handled by the peripheral itself
without the need for the CPU to continuously manage data feeding or retrieval in a
unitary way. Instead, the CPU needs to provide the full data frame to the peripheral in
one shot or read the full received data frame in one shot.
In such cases, the peripheral usually provides internal FIFOs and buffers that can
contain the full message or frame. It also provides flags and interrupts indicating that
the data frames are processed and available, as well as indicators on the FIFO
(Tx/Rx) levels in frames. This is the case with FDCAN peripherals, which provide
internal FIFOs and buffers, autonomously handle CAN frame sending and receiving,
and signal the user about the end of the process and the availability of data/frames
upon receiving.
In this scenario, a single monitoring process should be proposed instead of
conventional polling and interrupt-driven processes. The HAL driver should provide
the following:
• An API to start the peripheral
• Transmission or Writing Direction:
o An API to feed the entire data or frame to the internal peripheral FIFO or
buffer in one shot.
o An API to feed the entire data or frame to the internal peripheral FIFO or
buffer in one shot.
o API to enable the transmission/processing interrupts.
• Receiving or Reading Direction
o An API to read the entire received frame or data
o API to check if a new received frame is available or and the
receiving/processed output FIFO level (e.g., number of received frames)
o API to enable the receiving/processing interrupts
The user can implement the monitoring process flexibly at the application level using
either a blocking or non-blocking method.
• Blocking Method:
o Transmission or Writing Direction: Continuously check the internal Tx
FIFO level to know if the peripheral is ready to process/send a new
frame. Use the appropriate API to feed the peripheral with the new
frame to send.
o Receiving or Reading Direction: Continuously check the internal Rx
FIFO level to know if the peripheral received one or several frames and
retrieve them using the appropriate API.
• Non-Blocking Method:
o Transmission or Writing Direction: Enable the transmission/processing
frame complete interrupt(s). Within the corresponding callback, take
97

appropriate actions to check the Tx FIFO level and feed the peripheral
with the new frame(s) to send.
o Receiving or Reading Direction: Enable the receiving/processing
complete interrupt(s). Within the corresponding callback, take
appropriate actions to check the Rx FIFO level and read the received
frame(s) from the peripheral.
By following this approach, the user can implement a flexible and efficient monitoring
process at the application level.
Examples of user processing:
The monitoring model can also be useful for tracking additional events signaled by the
peripheral, in addition to the main data processes. In this case, the HAL driver should provide
APIs to start the monitoring process with or without interrupts, an API to check if a specific
event has been detected (useful for users who need to implement a monitoring task or loop),
and a dedicated callback function to signal the event (useful for users who prefer
asynchronous interception of the event). This approach allows users to implement a flexible
and efficient monitoring process at the application level, capable of handling both main data
processes and additional peripheral events, using either a blocking method by continuously
checking for events or a non-blocking method by relying on interrupts and callbacks for
asynchronous event handling.
98

Examples of user events monitoring:
99

100

11.4. HAL IRQ Handler and callback
11.4.1. HAL IRQ Handler
The HAL_PPP_IRQHandler() ISR function must be called from the corresponding PPPi_
IRQHandler (generated in mx_pppi.c) and manage the peripheral interrupt events and
maintain the processes states machine accordingly. When an interrupt event is asserted and
this later is associated to a functional state (error, completion, notification), a callback is called
to inform asynchronously the user about these events (refer to Registering user callbacks to the
HAL drivers).
When an interrupt is enabled, there are two models to handle it depending on the peripheral
interrupt hardware management:
Model1 (check for Interrupt sources register and events flags)
• Check for the interrupt sources bits
• Check for the event flag
• Clear the event status
• Process
void HAL_PPP_IRQHandler(hal_ppp_handle_t *hppp)
{
PPP_TypeDef *p_pppx= = PPP_GET_INSTANCE(handle);
uint32_t error_code = HAL_PPP_ERROR_NONE;
/* read the Interrupt enable register */
uint32_t ier_it = LL_PPP_READ_REG(p_pppx, ier_reg); /*IER: Interrut Enable register */
/* read the Interrupt status register */
uint32_t isrflags = LL_PPP_READ_REG(p_pppx, isr_reg); /*ISR: Interrut Status register */
/* PPP ERR1 error interrupt occurred -------------------------------------*/
if (((isrflags & PPP_ISR_ERR1) != 0U) && ((ier_it & PPP_IER_ERR1IE) != 0U))
{
LL_PPP_ClearFlag_ERR1(p_pppx); /* clear the ERR1 interrupt flag */
error_code = HAL_PPP_ERROR_ERR1;
}
...
/* PPP ERRn error interrupt occurred -------------------------------------*/
if (((isrflags & PPP_ISR_ERRn) != 0U) && ((ier_it & PPP_IER_ERRnIE) != 0U))
{
LL_PPP_ClearFlag_ERRn(p_pppx); /* clear the ERRn interrupt flag */
error_code |= HAL_PPP_ERROR_ERRn;
}
#if defined (USE_HAL_PPP_GET_LAST_ERRORS) && (USE_HAL_PPP_GET_LAST_ERRORS == 1)
hppp—>last_error_codes |= error_code;
#endif
if(error_code != HAL_PPP_ERROR_NONE)
{
/* call the Error callback */
#if defined (USE_HAL_PPP_REGISTER_CALLBACK) && (USE_HAL_PPP_REGISTER_CALLBACKS == 1)
hppp->p_error_cb(hppp);
#else
HAL_PPP_ErrorCallback(hppp);
#endif
}
...
/* Process the event */
if (((isrflags & PPP_ISR_EVENT1) != 0U) && ((ier_it & PPP_IER_EVENT1) != 0U))
{
LL_PPP_ClearFlag_EVENT1(p_pppx); /* clear the EVENT1 interrupt flag */
#if defined (USE_HAL_PPP_REGISTER_CALLBACK) && (USE_HAL_PPP_REGISTER_CALLBACKS == 1U)
hppp->p_event#i_cb(hppp);
#else
HAL_PPP_Event#iCallback(hppp);
101

#endif /* USE_HAL_PPP_REGISTER_CALLBACK == 1U */
}
/* Process completion */
if (((isrflags & PPP_ISR_COMPLETION_MSK) != 0U) && ((ier_it & PPP_IER_COMPLETION_MSK) != 0U))
{
LL_PPP_ClearFlag_COMPLETION(p_pppx); /* clear the comletion flags */
/* Disable the process interrupts */
LL_PPP_DisableIT (p_pppx, completion_msk); /* or can use LL_PPP_READ_REG/ LL_PPP_WRITE_REG to
disable the given process interrupts in the IER: Interrut Enable register */
/* update the global state to IDLE */
hppp->global_state = HAL_PPP_STATE_IDLE; /* case of a single process at a time */
/* or update the process state to IDLE */
hppp->{process#i}_state = HAL_PPP_STATE_{PROCESS#i}_IDLE;
#if defined (USE_HAL_PPP_REGISTER_CALLBACK) && (USE_HAL_PPP_REGISTER_CALLBACKS == 1U)
hppp->p_process#i_cplt_cb(hppp);
#else
HAL_PPP_Process#iCpltCallback(hppp);
#endif /* USE_HAL_PPP_REGISTER_CALLBACK == 1U */
}
}
▪ Model2 (check Interrupt Status Register)
• Check for the interrupt status
• Clear the interrupt status
• Process
void HAL_PPP_IRQHandler(hal_ppp_handle_t *hppp)
{
PPP_TypeDef *p_pppx= = PPP_GET_INSTANCE(handle);
uint32_t error_code = HAL_PPP_ERROR_NONE;
uint32_t isrflags = LL_ReadReg(p_pppx, <status_reg>);
/* Knoning that the error code values are mapped/defined as the Error register Fields */
error_code = LL_ReadReg(p_pppx, <err_reg>);
LL_PPP_ClearFlags(p_pppx); /* clear the interrupt flags */
if (PPP_CHECK_FLAG(error_code, PPP_FLAG_<ERR1>))
{
error_code = HAL_PPP_ERROR_ERR1
}
...
if (PPP_CHECK_FLAG(error_code, PPP_FLAG_<ERRn>))
{
error_code |= HAL_PPP_ERROR_ERRn
}
#if defined (USE_HAL_PPP_GET_LAST_ERRORS) && (USE_HAL_PPP_GET_LAST_ERRORS == 1)
hppp—>last_error_codes |= error_code;
#endif
if(error_code != HAL_PPP_ERROR_NONE)
{
#if defined (USE_HAL_PPP_REGISTER_CALLBACK) && (USE_HAL_PPP_REGISTER_CALLBACKS == 1U)
hppp->p_error_cb(hppp);
#else
HAL_PPP_ErrorCallback(hppp);
#endif /* USE_HAL_PPP_REGISTER_CALLBACK == 1U */
}
/* Process the event */
if (PPP_CHECK_FLAG(isrflags, PPP_FLAG_EVENT1) != RESET)
{
102

#if defined (USE_HAL_PPP_REGISTER_CALLBACK) && (USE_HAL_PPP_REGISTER_CALLBACKS == 1U)
hppp->p_event#1_cb(hppp);
#else
HAL_PPP_Event#1Callback(hppp);
#endif /* USE_HAL_PPP_REGISTER_CALLBACK == 1U */
}
/* Process completion */
if ((isrflags & PPP_ISR_COMPLETION_MSK) != 0U)
{
/* Disable the process interrupts */
LL_PPP_DisableIT (p_pppx);
/* update the global state to IDLE */
hppp->global_state = HAL_PPP_STATE_IDLE; /* case of a single process at a time */
/* or update the process state to IDLE */
hppp->{process#i}_state = HAL_PPP_STATE_{PROCESS#i}_IDLE;
#if defined (USE_HAL_PPP_REGISTER_CALLBACK) && (USE_HAL_PPP_REGISTER_CALLBACKS == 1U)
hppp->p_process#i_cplt_cb(hppp);
#else
HAL_PPP_Process#iCpltCallback(hppp);
#endif /* USE_HAL_PPP_REGISTER_CALLBACK == 1U */
}
}
Notes: Interrupt and flag registers must be read once and saved locally to prevent race
condition and optimize the registers access within IRQ handlers.
11.4.2. HAL callbacks
The asynchronous process models (Interrupt model and DMA model) must allow
synchronization with the user application through dedicated callbacks. HAL callbacks are
invoked by the HAL PPP driver when the corresponding event occurs. A separate callback
should be provided for each event, including process completion, half-completion, abort
completion, and error handling. For some peripherals, callbacks should also cover
asynchronous events related to hardware control and monitoring. For example, the HAL
LTDC should provide a callback to signal that the LTDC has reached a specific line during
display, and the HAL FDCAN should inform when frames are received.
The HAL should enable users to implement the required callback behaviour for their
applications. To achieve this, a HAL PPP driver that provides an asynchronous model should
offer the following:
• Required Callbacks as Weak Empty Functions: These can be overridden by the user
with their implementation.
• Required Callbacks as Pointers to User Functions: Users can implement these
callbacks, and the HAL PPP driver should provide APIs to allow users to save or
register these function pointers into the HAL PPP handle. This case must available
under dedicated compilation switches by HAL PPP driver to reduce the impact of the
HAL PPP handle RAM footprint.
For a given event callback, both weak and pointer-to-function callbacks must adhere to the
same prototype. However, it is permissible for two different callbacks within different scopes
to have different prototypes. Despite this allowance, it is highly recommended to minimize the
diversity of callback prototypes within the same driver and to harmonize them. For example,
103

in the HAL TIM driver, callbacks can be grouped into two categories: those related to TIMER
global events (with the handle as the unique parameter) and those related to TIMER channel
events (with the handle and the channel as parameters). This approach promotes consistency
and simplifies the management of callbacks within the same driver.
In both cases (weak functions or pointers to user functions), the various callbacks must be
triggered through the HAL_PPP_IRQHandler or the DMA callback when the corresponding
event occurs:
• Explicitly Signaled by a Given Interrupt within the HAL_PPP_IRQhandler: In
some cases, additional information, such as the value of a counter stored in the handle
and incremented within the HAL_PPP_IRQHandler, may be required to identify the
end of the process and call the corresponding callback.
• Triggered by a DMA Callback: This is implemented within the HAL PPP driver
according to the DMA model, meaning that the implementation of the DMA callback
within the HAL PPP driver will call the user HAL PPP callback.
Notes:
At the Applications/Examples level, the necessary resources (such as DMA, GPIO,
NVIC, and CLOCK) for the peripheral sequence should be configured either before
calling HAL_PPP_Init or between the calls
to HAL_PPP_Init and HAL_PPP_SetConfig. This is done by the code generation
within the pppi_init generated function
Respectively, the deinitialization sequence of these resources must be done after the call
to HAL_PPP_DeInit
Note: context for HAL2 versus HAL1 , the MSP Init and DeInit Callback are removed
on HAL2 versus HAL1.
11.4.2.1. Weak callback model
The user callback functions are defined as empty functions with “weak” attribute. When a
callback is needed, it must be overridden in the user code.
Event Callback functions Example
Process completed HAL_PPP_ProcessCpltCallback HAL_USART_TxCpltCallback
Process half completed HAL_PPP_ProcessHalfCpltCallback HAL_USART_TxHalfCpltCallback
Process aborted HAL_PPP_AbortCpltCallback (if we provide one HAL_USART_AbortCpltCallback
single HAL_PPP_Abort )
Or HAL_PPP_ProcessAbortCpltCallback (if we
provide HAL_PPP_AbortProcess by process )
HAL_UART_TxAbortCpltCallback
HAL_UART_RxAbortCpltCallback
Process error HAL_PPP_ErrorCallback HAL_USART_ErrorCallback
104

Aysnc control/monitoring HAL_PPP_EventCallback HAL_LTDC_LineDetectionCallback
event
HAL_TIM_BreakCallback
By default, the HAL is based on the weak empty function declared at the HAL PPP driver and
overridden by the user if necessary. With this behaviour, one single callback for all instances
of a given peripheral. This method implicates an inter-dependences between application
modules. When each module uses an instance of a given peripheral; if the weak callback is
overridden in an application module, it is no longer possible to surcharge it for another module
(example: case of overridden callbacks in a part IO interface module).
Example:
/**
* @brief Tx Transfer completed callback.
* @param husart Pointer to a \ref hal_usart_handle_t structure.
*/
__WEAK void HAL_USART_TxCpltCallback(hal_usart_handle_t *husart)
{
/* Prevent unused argument(s) compilation warning */
STM32_UNUSED(husart);
/** @warning This function must not be modified, when the callback is needed,
* the HAL_USART_TxCpltCallback() can be implemented in the user file.
*/
}
11.4.2.2. Register callback model.
In this model, by enabling the USE_HAL_PPP_REGISTER_CALLBACKS defines (one
define per peripheral), users can dynamically choose their own callbacks for the different
features in their HAL PPP driver. The dynamic callbacks are instance-dependent instead of
peripheral-dependent, allowing the end user to define different callback functions for each
instance of a given peripheral, rather than one global weak (overridden) callback for all
instances of a peripheral. Users can change/customize callbacks independently for each
peripheral instance using the HAL_PPP_RegisterEvent#iCallback function (one register
function corresponding to each event “i” callback).
Note that the different callback function pointers in the handles are initialized/reset by default
to the legacy weak (overridden) callbacks within the HAL_PPP_Init. Once the user registers
their own callbacks, using HAL_PPP_RegisterEvent#iCallback also allows restoring the
default behavior (global weak/overridden callback). This is possible by providing the default
global weak/overridden callback as a parameter to the HAL_PPP_RegisterEvent#iCallback .
This means that there is no need for an unregister callback function provided by the HAL PPP
driver; users should rely on the same register callback function to restore the default one.
The HAL PPP driver must provide prototypes for the various callbacks. It must store these
callbacks into the handle and provide
corresponding HAL_PPP_RegisterEvent_iCallback functions for each event “i” based on the
corresponding callback prototype. The entire implementation must be under
the USE_HAL_PPP_REGISTER_CALLBACKS compilation switch.
Examples
• Callbacks prototypes
105

typedef struct hal_uart_handle_s hal_uart_handle_t;
#if defined(USE_HAL_UART_REGISTER_CALLBACKS) && (USE_HAL_UART_REGISTER_CALLBACKS == 1)
/*! HAL UART Generic UART callback Type */
typedef void (* hal_uart_cb_t)(hal_uart_handle_t *huart);
/*! HAL UART Reception Complete Callback Pointer Type */
typedef void (* hal_uart_rx_cplt_cb_t)(hal_uart_handle_t *huart, uint16_t size_byte,
hal_uart_rx_event_types_t rx_event);
#endif /* USE_HAL_UART_REGISTER_CALLBACKS */
• Callbacks pointer storage into the handle
struct hal_uart_handle_s
{
…
#if defined(USE_HAL_UART_REGISTER_CALLBACKS) && (USE_HAL_UART_REGISTER_CALLBACKS == 1)
/*! USART Tx Half Complete Callback */
hal_uart_cb_t p_tx_half_cplt_cb;
/*! USART Tx Complete Callback */
hal_uart_cb_t p_tx_cplt_cb;
/*! USART Rx Half Complete Callback */
hal_uart_cb_t p_rx_half_cplt_cb;
/*! USART Rx Complete Callback */
hal_uart_rx_cplt_cb_t p_rx_cplt_cb;
...
#endif /* USE_HAL_UART_REGISTER_CALLBACKS */
...
}
• Callback pointers initialization within the HAL_PPP_Init:
hal_status_t HAL_UART_Init(hal_uart_handle_t *huart, hal_uart_t instance)
{
...
#if defined(USE_HAL_UART_REGISTER_CALLBACKS) && (USE_HAL_UART_REGISTER_CALLBACKS == 1)
/* Init the UART Callback settings */
huart->p_tx_half_cplt_cb = HAL_UART_TxHalfCpltCallback; /* Legacy weak TxHalfCpltCallback */
huart->p_tx_cplt_cb = HAL_UART_TxCpltCallback; /* Legacy weak TxCpltCallback */
huart->p_rx_half_cplt_cb = HAL_UART_RxHalfCpltCallback; /* Legacy weak RxHalfCpltCallback */
huart->p_rx_cplt_cb = HAL_UART_RxCpltCallback; /* Legacy weak RxCpltCallback */
...
#endif /* (USE_HAL_UART_REGISTER_CALLBACKS) */
...
}
Note: It is not required to reset the callback pointer within the HAL_PPP_DeInit. In any case,
a call to HAL_PPP_Init is required to use the given handle again, and the callbacks
initialization is already done within the HAL_PPP_Init.
• Callback register functions:
/**
* @brief Register the UART Tx Half Complete Callback
* @param huart Pointer to a \ref hal_uart_handle_t structure which contains the UART instance.
* @param p_callback pointer to the Tx Half Complete Callback function
* @retval HAL_OK The function has been registered.
* @retval HAL_INVALID_PARAM p_callback is NULL.
*/
hal_status_t HAL_UART_RegisterTxHalfCpltCallback(hal_uart_handle_t *huart, hal_uart_cb_t p_callback)
{
ASSERT_DBG_PARAM(huart != NULL);
ASSERT_DBG_PARAM(p_callback != NULL);
ASSERT_DBG_STATE(huart->global_state, (uint32_t)(HAL_UART_STATE_CONFIGURED | HAL_UART_STATE_INIT));
ASSERT_DBG_STATE(huart->rx_state, (uint32_t)(HAL_UART_RX_STATE_IDLE | HAL_UART_RX_STATE_RESET));
ASSERT_DBG_STATE(huart->tx_state, (uint32_t)(HAL_UART_TX_STATE_IDLE | HAL_UART_TX_STATE_RESET));
#if defined(USE_HAL_CHECK_PARAM) && (USE_HAL_CHECK_PARAM == 1)
if (p_callback == NULL)
{
106

return HAL_INVALID_PARAM;
}
#endif /* USE_HAL_CHECK_PARAM */
huart->p_tx_half_cplt_cb = p_callback;
return HAL_OK;
}
11.4.2.3. Callbacks usage and policy
Within the HAL_PPP_IRQHandler, when an interrupt event is asserted and is associated with
a functional state (such as error, completion, abortion, or event notification), the corresponding
callback must be called to asynchronously inform the user about these events.
Depending on the compilation settings, specifically whether
USE_HAL_PPP_REGISTER_CALLBACKS is defined, the HAL_PPP_IRQHandler must
either call the global weak (overridden) callback or the registered callback.
• Case of an asynchronous event
void HAL_PPP_IRQHandler(hal_ppp_handle_t *hppp)
{
PPP_TypeDef *p_pppx= = PPP_GET_INSTANCE(handle);
...
/* Process the event */
if (((isrflags & PPP_ISR_EVENT1) != 0U) && ((ier_it & PPP_IER_EVENT1) != 0U))
{
LL_PPP_ClearFlag_EVENT1(p_pppx); /* clear the EVENT1 interrupt flag */
#if defined (USE_HAL_PPP_REGISTER_CALLBACK) && (USE_HAL_PPP_REGISTER_CALLBACKS == 1U)
hppp->p_event#i_cb(hppp);
#else
HAL_PPP_Event#iCallback(hppp);
#endif /* USE_HAL_PPP_REGISTER_CALLBACK == 1U */
}
...
}
• case of process completion
void HAL_PPP_IRQHandler(hal_ppp_handle_t *hppp)
{
PPP_TypeDef *p_pppx= = PPP_GET_INSTANCE(handle);
...
/* Process completion */
if (((isrflags & PPP_ISR_COMPLETION_MSK) != 0U) && ((ier_it & PPP_IER_COMPLETION_MSK) != 0U))
{
LL_PPP_ClearFlag_COMPLETION(p_pppx); /* clear the completion flags */
/* Disable the process interrupts */
LL_PPP_DisableIT (p_pppx, completion_msk);
/* update the global state to IDLE */
hppp->global_state = HAL_PPP_STATE_IDLE; /* case of a single process at a time */
/* or update the process state to IDLE */
hppp->{process#i}_state = HAL_PPP_STATE_{PROCESS#i}_IDLE;
#if defined (USE_HAL_PPP_REGISTER_CALLBACK) && (USE_HAL_PPP_REGISTER_CALLBACKS == 1U)
hppp->p_process#i_cplt_cb(hppp);
#else
HAL_PPP_Process#iCpltCallback(hppp);
#endif /* USE_HAL_PPP_REGISTER_CALLBACK == 1U */
}
...
}
107

• Case of error
void HAL_PPP_IRQHandler(hal_ppp_handle_t *hppp)
{
PPP_TypeDef *p_pppx= = PPP_GET_INSTANCE(handle);
uint32_t error_code = HAL_PPP_ERROR_NONE;
...
/* PPP ERRn error interrupt occurred -------------------------------------*/
if (((isrflags & PPP_ISR_ERRn) != 0U) && ((ier_it & PPP_IER_ERRnIE) != 0U))
{
LL_PPP_ClearFlag_ERRn(p_pppx); /* clear the ERRn interrupt flag */
error_code |= HAL_PPP_ERROR_ERRn;
}
#if defined (USE_HAL_PPP_GET_LAST_ERRORS) && (USE_HAL_PPP_GET_LAST_ERRORS == 1)
hppp—>last_error_codes |= error_code;
#endif
if(error_code != HAL_PPP_ERROR_NONE)
{
/* call the Error callback */
#if defined (USE_HAL_PPP_REGISTER_CALLBACK) && (USE_HAL_PPP_REGISTER_CALLBACKS == 1)
hppp->p_error_cb(hppp);
#else
HAL_PPP_ErrorCallback(hppp);
#endif
}
...
}
Note for callback usage: As the callback is invoked in the context of an interrupt, the
implementation within the callbacks must be as short and brief as possible. Ideally, the
callback should signal the corresponding event to the various application modules and tasks
(executed in thread mode) and return immediately. This can be achieved through semaphores
in RTOS-based applications or equivalent mechanisms in bare-metal applications.
Concrete Implementation of Callbacks:
• Must Not:
o Implement a process such as data processing or comparing.
o Call blocking HAL APIs.
o Initiate any treatment based on the HAL timebase to avoid issues regarding
interrupt priorities between the HAL timebase and the current interrupt from
which the callback is invoked.
• Can:
o Initiate a non-blocking process such as HAL Interrupt and DMA-based
processes.
11.5. Optional Features control APIs
Additional optional features can be provided by the peripheral that requires a configuration to
control the behavior of the peripheral, these features are not mandatory to start a process but
rather allow to change the behavior of the peripheral (Ex: allowing the peripheral to continue
working in low power mode). Dedicated feature configuration APIs must be provided to allow
user applying or retrieving these features parameters. The following describes the APIs
naming rules according to the various use cases:
108

11.5.1. Features that take effect immediately:
This applies for features that can be applied immediately and changed at-will by the
application without disabling it (the feature) prior to change the corresponding parameters. For
multiple parameters, the APIs use a pointer to a configuration structure. For single parameters,
the APIs take the parameter directly. For multiple parameters (up to 4), the APIs accept them
in a row.
• Multiple Parameters (using structure):
hal_status_t HAL_PPP_Set{Feature}(hal_ppp_handle_t *hppp, hal_ppp_{feature}_config_t *p_config);
void HAL_PPP_Get{Feature}(hal_ppp_handle_t *hppp, hal_ppp_{feature}_config_t *p_config);
• Single Parameter:
hal_status_t HAL_PPP_Set{Feature}(hal_ppp_handle_t *hppp, param_type param);
param_type HAL_PPP_Get{Feature}(hal_ppp_handle_t *hppp);
• Multiple Parameters:
Also accepted to pass up to 4 parameters in row but the recommendation is to encapsulate in a
structure
hal_status_t HAL_PPP_Set{Feature}(hal_ppp_handle_t *hppp, param_type param1, ..., param_type parami);
void HAL_PPP_Get{Feature}(hal_ppp_handle_t *hppp, param_type *param1, ..., param_type *parami);
• Examples:
hal_status_t HAL_I2C_SetDigitalFilter(hal_i2c_handle_t *hi2c, uint32_t value);
uint32_t HAL_I2C_GetDigitalFilter(const hal_i2c_handle_t *hi2c);
hal_status_t HAL_TIM_SetSynchroSlave(hal_tim_handle_t *htim, const hal_tim_slave_config_t *p_config);
void HAL_TIM_GetSynchroSlave(const hal_tim_handle_t *htim, hal_tim_slave_config_t *p_config);
hal_status_t HAL_TIM_SetDeadtime(hal_tim_handle_t *htim,
uint32_t rising_edge_deadtime,
uint32_t falling_edge_deadtime);
void HAL_TIM_GetDeadtime(const hal_tim_handle_t *htim,
uint32_t *p_rising_edge_deadtime,
uint32_t *p_falling_edge_deadtime);
11.5.1. Features that can be enabled or disabled:
• Enable/Disable APIs:
Without any parameter:
hal_status_t HAL_PPP_Enable{Feature}(hal_ppp_handle_t *hppp);
hal_status_t HAL_PPP_Disable{Feature}(hal_ppp_handle_t *hppp);
hal_ppp_{feature}_status_t HAL_PPP_IsEnabled{Feature}(hal_ppp_handle_t *hppp);
or with an additional parameter
hal_status_t HAL_PPP_Enable{Feature}(hal_ppp_handle_t *hppp, param_type mode);
hal_status_t HAL_PPP_Disable{Feature}(hal_ppp_handle_t *hppp);
hal_ppp_{feature}_status_t HAL_PPP_IsEnabled{Feature}(hal_ppp_handle_t *hppp);
param_type HAL_PPP_Get{Feature}{Mode}(hal_ppp_handle_t *hppp);
• Examples:
109

hal_status_t HAL_TIM_EnableOnePulseMode(hal_tim_handle_t *htim);
hal_status_t HAL_TIM_DisableOnePulseMode(hal_tim_handle_t *htim);
hal_tim_one_pulse_mode_status_t HAL_TIM_IsEnabledOnePulseMode(const hal_tim_handle_t *htim);
hal_status_t HAL_RCC_MSIS_Enable(hal_rcc_msis_range_t clock_range);
hal_status_t HAL_RCC_MSIS_Disable(void);
hal_rcc_osc_enable_status_t HAL_RCC_MSIS_IsEnabled(void);
hal_rcc_msis_range_t HAL_RCC_MSIS_GetRange(void);
11.5.1. Features that require configuration and Enable/Disable split
This case is for configuring feature parameters without enabling the feature immediately. The
feature must be disabled before setting a new configuration and then enabled when needed
(without the obligation to re-configure). For multiple parameters, the APIs use a pointer to a
configuration structure. For single parameters, the APIs take the parameter directly. For
multiple parameters (up to 4), the APIs accept them in a row.
• Single Parameter:
hal_status_t HAL_PPP_SetConfig{Feature}(hal_ppp_handle_t *hppp, param_type param);
param_type HAL_PPP_GetConfig{Feature}(hal_ppp_handle_t *hppp);
• Multiple Parameters:
hal_status_t HAL_PPP_SetConfig{Feature}(hal_ppp_handle_t *hppp,
const hal_ppp_{feature}_config_t *p_config);
void HAL_PPP_GetConfig{Feature}(hal_ppp_handle_t *hppp, hal_ppp_{feature}_config_t *p_config);
Also accepted to pass up to 4 parameters in row but the recommendation is to encapsulate in a
structure
hal_status_t HAL_PPP_SetConfig{Feature}(hal_ppp_handle_t *hppp,
param_type param1,
...,
param_type parami);
void HAL_PPP_GetConfig{Feature}(hal_ppp_handle_t *hppp, param_type *param1, ..., param_type *parami);
• Examples:
hal_status_t HAL_UART_SetConfigReceiverTimeout(const hal_uart_handle_t *huart, uint32_t timeout_bit);
uint32_t HAL_UART_GetConfigReceiverTimeout(const hal_uart_handle_t *huart);
hal_status_t HAL_UART_EnableReceiverTimeout(const hal_uart_handle_t *huart);
hal_status_t HAL_UART_DisableReceiverTimeout(const hal_uart_handle_t *huart);
hal_uart_receiver_timeout_status_t HAL_UART_IsEnabledReceiverTimeout(const hal_uart_handle_t *huart);
hal_status_t HAL_SPI_SetConfigCRC(hal_spi_handle_t *hspi, const hal_spi_crc_config_t *p_config);
void HAL_SPI_GetConfigCRC(const hal_spi_handle_t *hspi, hal_spi_crc_config_t *p_config);
hal_status_t HAL_SPI_EnableCRC(hal_spi_handle_t *hspi);
hal_status_t HAL_SPI_DisableCRC(hal_spi_handle_t *hspi);
hal_spi_crc_status_t HAL_SPI_IsEnabledCRC(hal_spi_handle_t *hspi);
hal_status_t HAL_I2C_SetConfigOwnAddress2(hal_i2c_handle_t *hi2c,
uint32_t addr,
hal_i2c_own_addr2_mask_t mask);
void HAL_I2C_GetConfigOwnAddress2(const hal_i2c_handle_t *hi2c,
uint32_t *addr,
hal_i2c_own_addr2_mask_t *mask);
hal_status_t HAL_I2C_EnableOwnAddress2(hal_i2c_handle_t *hi2c);
hal_status_t HAL_I2C_DisableOwnAddress2(hal_i2c_handle_t *hi2c);
hal_i2c_own_addr2_status_t HAL_I2C_IsEnabledOwnAddress2(const hal_i2c_handle_t *hi2c);
110

11.6. HAL Programming model
11.6.1. User parameters validity check
The HAL APIs should check the input parameters using assertions. ASSERT_DBG_PARAM
should be used to check the validity of parameters (including NULL pointers). The HAL APIs
should also check the validity of the current state for a given operation (configuration or
process) using assertions. ASSERT_DBG_STATE should be used to check the state validity.
Example:
hal_status_t HAL_PPP_Process(hal_ppp_handle_t *hppp, const void *p_data, uint32_t size_byte, uint32_t
timeout_ms)
{
/* Check the PPP handle & parameters */
ASSERT_DBG_PARAM((hppp != NULL));
ASSERT_DBG_PARAM((p_data != NULL));
ASSERT_DBG_PARAM((size_byte != 0));
/* Check the global state */
ASSERT_DBG_STATE(hppp->global_state, HAL_PPP_STATE_IDLE);
...
}
Example of checking several states by asserts
hal_status_t HAL_PPP_SetConfig(hal_ppp_handle_t *hppp, const hal_ppp_config_t *p_config)
{
/* Check the PPP handle & parameters */
ASSERT_DBG_PARAM((hppp != NULL));
ASSERT_DBG_PARAM((p_config != NULL));
ASSERT_DBG_PARAM(IS_PPP_PARAM(p_config->param));
/* Check the global state */
ASSERT_DBG_STATE(hppp->state, (uint32_t)HAL_PPP_STATE_INIT \
| (uint32_t)HAL_PPP_STATE_IDLE);
...
}
11.6.2. State machine
When a HAL driver is built around a handle object, a state machine must be provided to
reflect the driver's functional states. The usage of the state machine must adhere to the
following principles:
• State Transition Management: A state machine must be used to ensure proper
transitions between the driver's functional states. This helps maintain a clear and
controlled flow of operations within the driver.
• Not for Lock Mechanism: The state machine should not be used as a lock
mechanism. Its purpose is to manage state transitions, not to control access to
resources.
• Not for Identifying Functional Modes: The state machine should not be used to
identify functional modes (e.g., I2C master/slave mode). Functional modes should be
managed separately from the state machine.
111

• Unitary States: The states must be unitary, relative to a single process step. The state
variable must handle one state at a time, meaning mixing different states is not
allowed.
• Dedicated Assert for State Checks: State checks must be done through dedicated
assertions, allowing the footprint to be reduced when not in debug mode. This ensures
that state validation does not impact performance in production builds
11.6.2.1. global state machine
Each HAL driver must provide a global state machine with the following minimum states to
manage the driver's functional states effectively:
• HAL_PPP_STATE_RESET = 0: This is the default state when the handle is not
initialized yet with the appropriate HAL_PPP_Init function (before the HAL_PPP_Init
function returns). It is also the state that must be set during
the HAL_PPP_DeInit() service. This state indicates that the driver is in its default,
uninitialized state. The value must be zero as this state must indicate that we are snot
initialized yet.
• HAL_PPP_STATE_INIT: The appropriate HAL_PPP_Init function must apply this
state when the initialization is performed. This involves resetting the handle object and
linking it to the physical instance. This state indicates that the HAL handle is
initialized but the corresponding peripheral instance not yet ready to start a process.
Note that some peripherals like the CRC comes with a functional configuration out of
reset. In this case, the HAL PPP state machine does not need to provide
a HAL_PPP_INIT_STATE. Instead, the HAL_PPP_Init function sets the state directly
to IDLE
• HAL_PPP_STATE_IDLE: This state must be applied by a global configuration API,
such as HAL_PPP_SetConfig. It indicates that a global configuration has been applied,
and the driver is ready to start a process that does not require a sub-block
configuration. Examples UART transmit or I2C receive operations.
• HAL_PPP_STATE_FAULT: This state indicates that the peripheral has encountered
a fatal error that requires a recovery sequence in the application code. This state must
only be provided if the peripheral can encounter a non-recoverable blocking error that
necessitates an applicative recovery sequence followed by a full HAL PPP re-
initialization sequence i.e HAL_PPP_DeInit, HAL_PPP_Init. If the peripheral does not
have such errors, this state should not be included.
The following illustration demonstrates how to implement the global state declaration and
store it inside the HAL PPP handle.
typedef enum
{
HAL_PPP_STATE_RESET = 0, /*!< PPP is not yet Initialized or De-Initialized */
HAL_PPP_STATE_INIT = (1U << 31U), /*!< PPP is initialized but not yet configured */
HAL_PPP_STATE_IDLE = (1U << 30U), /*!< PPP initialized and a global config applied */
HAL_PPP_STATE_FAULT = (1U << 27U) /*!< PPP encountered an unrecoverable error and
a recovery sequence is needed */
} hal_ppp_state_t;
112

Note: except the RESET state that must be zero to indicate that we are not initialized yet; other
states values must be implemented as bit mapped instead of incremental integer allowing to
ASSERT on different states. Additionally we start from the highest possible value (1 << 31) to
ensure that the state is represented by a 32 bits in all cases and avoid MISRA-C issues when
asserting different states.
The global state is stored within the HAL PPP handle structure, which links the state machine
to the peripheral instance. The keyword volatile must be used as the state can evolve within an
interrupt context.
struct hal_ppp_handle_s
{
hal_ppp_t instance; /*!< Peripheral instance */
volatile hal_ppp_state_t global_state; /*!< PPP global state */
// Additional members can be added here
...
};
A “HAL_PPP_GetState” must be provided allowing to retrieve the global state:
/**
* @brief Retrieve the HAL PPP Global State.
* @param hppp Pointer to a hal_ppp_handle_t structure, handle of the specified PPP.
* @retval hal_ppp_state_t HAL PPP Global State
*/
hal_ppp_state_t HAL_PPP_GetState(hal_ppp_handle_t *hppp)
{
/* Check the PPP handle allocation */
ASSERT_DBG_PARAM(hppp != NULL);
return hppp->global_state;
}
IMPORTANT: The HAL_PPP_GetState() service is provided for monitoring purposes to
indicate the current state of the driver. It must not be used for process synchronization to avoid
any thread safety issues. Synchronization and resources sharing should be handled internally
by the applicative processes themselves and using HAL_PPP_AcquireBus/
HAL_PPP_ReleaseBus services for the bus drivers.
Note: Both HAL_PPP_Init and HAL_PPP_DeInit must not check the state(s) (Global state,
process states or sub-instances states) using ASSERT. The HAL_PPP_Init function serves as
the entry point to the driver, being the first function called to start using the driver.
Conversely, the HAL_PPP_DeInit function serves as the exit point, allowing the user to stop
using the driver. Therefore, it is meaningless and prohibited to check the state(s) using
assertions within these functions.
113

11.6.2.2. case of single process at a time
When the peripheral allows a single process at a time (e.g., I2C), the global state machine
must be extended to include the different process states. This ensures that the driver can
accurately reflect the current operation being performed by the peripheral.
Example:
typedef enum
{
HAL_I2C_STATE_RESET = (0UL), /*!< Not yet Initialized */
HAL_I2C_STATE_INIT = (1UL << 31), /*!< Initialized but not yet configured */
HAL_I2C_STATE_IDLE = (1UL << 30), /*!< Initialized and a global config applied */
HAL_I2C_STATE_TX = (1UL << 29), /*!< Data Transmission process is ongoing */
HAL_I2C_STATE_RX = (1UL << 28), /*!< Data Reception process is ongoing */
HAL_I2C_STATE_LISTEN = (1UL << 27), /*!< Address Listen Mode is ongoing */
HAL_I2C_STATE_TX_LISTEN = (1UL << 26), /*!< Address Listen for Transmission ongoing */
HAL_I2C_STATE_RX_LISTEN = (1UL << 25), /*!< Address Listen for Reception ongoing */
HAL_I2C_STATE_ABORT = (1UL << 24), /*!< Abort user request
ongoing */
} hal_i2c_state_t;
Initializing and resetting the global state:
The HAL_PPP_Init function must set the global state to HAL_PPP_STATE_INIT. This
action must be performed at the end of the function, immediately before returning. This
ensures that all required settings are applied, and the handle is fully initialized
The HAL_PPP_DeInit function should reset the global state to HAL_PPP_STATE_RESET.
This action must be performed at the end of the function (last instruction). This ensures
that all required actions, such as stopping any ongoing operations, clearing flags, and disabling
interrupts, are completed.
Example:
hal_status_t HAL_I2C_Init(hal_i2c_handle_t *hi2c, hal_i2c_t instance)
{
ASSERT_DBG_PARAM((hi2c != NULL));
ASSERT_DBG_PARAM(IS_I2C_ALL_INSTANCE((I2C_TypeDef *)((uint32_t)instance)));
...
hi2c->global_state = HAL_I2C_STATE_INIT;
return HAL_OK;
}
void HAL_I2C_DeInit(hal_i2c_handle_t *hi2c)
{
ASSERT_DBG_PARAM((hi2c != NULL));
ASSERT_DBG_PARAM(IS_I2C_ALL_INSTANCE((I2C_TypeDef *)((uint32_t) hi2c->instance)));
...
hi2c->global_state = HAL_I2C_STATE_RESET;
}
Updating the global state when applying the global configuration:
The HAL_PPP_SetConfig function must verify that the global state is either
HAL_PPP_STATE_INIT or HAL_PPP_STATE_IDLE before applying a new configuration.
114

After successfully applying the new configuration, the global state should be set to
HAL_PPP_STATE_IDLE.
Note: The same principle about updating the state applies here. The state must be set to
HAL_PPP_STATE_IDLE at the end of the HAL_PPP_SetConfig function, immediately
before returning. This ensures that all settings are applied to the peripheral and any handle
fields before updating the state.
Example:
hal_status_t HAL_I2C_SetConfig(hal_i2c_handle_t *hi2c, const hal_i2c_config_t *p_config)
{
I2C_TypeDef *p_i2cx;
ASSERT_DBG_PARAM((hi2c != NULL));
ASSERT_DBG_PARAM(...);
ASSERT_DBG_STATE(hi2c->global_state, (uint32_t)HAL_I2C_STATE_INIT | (uint32_t)HAL_I2C_STATE_IDLE);
p_i2cx = I2C_GET_INSTANCE(hi2c);
...
LL_I2C_Enable(p_i2cx);
hi2c->global_state = HAL_I2C_STATE_IDLE;
return HAL_OK;
}
Moving the global state during a blocking process execution:
A blocking process API must verify that the global state is HAL_PPP_STATE_IDLE before
starting. The state should then be updated to reflect the various process steps required to
accomplish the given process (typically, a single step such as
HAL_PPP_STATE_{PROCESS#i}_ACTIVE).
At the end of the process, the state must be set back to HAL_PPP_STATE_IDLE regardless of
the process status (success or error), except when a HAL_PPP_STATE_FAULT state is
provided and in the case of an unrecoverable error (the peripheral enters a fail-stop condition
and requires a recovery sequence to be executed by the user).
Example:
hal_status_t HAL_USART_Transmit(hal_usart_handle_t *husart, const void *p_data, uint32_t size_byte,
uint32_t timeout_ms)
{
ASSERT_DBG_PARAM(husart != NULL);
...
ASSERT_DBG_STATE(husart->global_state, HAL_USART_STATE_IDLE);
HAL_CHECK_UPDATE_STATE(husart, global_state, HAL_USART_STATE_IDLE, HAL_USART_STATE_TX_ACTIVE);
/* At end of Tx process, restore husart->global_state to Idle */
husart->global_state = HAL_USART_STATE_IDLE;
return status;
}
Moving the global state during a non-blocking IT/DMA process execution:
A non-blocking process API (using Interrupt or DMA) must verify that the global state is
"IDLE" before starting. Once verified, the state should be set to the initial process step
(typically a single step, such as HAL_PPP_STATE_{PROCESS#i}_ACTIVE). If an error
115

occurs that prevents the process from starting, the global state must be restored to "IDLE", and
the API should return HAL_ERROR.
Example:
hal_status_t HAL_USART_Transmit_IT(hal_usart_handle_t *husart, const void *p_data, uint32_t size_byte)
{
ASSERT_DBG_PARAM(husart != NULL);
ASSERT_DBG_PARAM(p_data != NULL);
ASSERT_DBG_PARAM(size_byte != 0);
ASSERT_DBG_STATE(husart->global_state, HAL_USART_STATE_IDLE);
#if defined(USE_HAL_CHECK_PARAM) && (USE_HAL_CHECK_PARAM == 1)
if ((p_data == NULL) || (size_byte == 0U))
{
return HAL_INVALID_PARAM;
}
#endif /* USE_HAL_CHECK_PARAM */
HAL_CHECK_UPDATE_STATE(husart, global_state, HAL_USART_STATE_IDLE, HAL_USART_STATE_TX_ACTIVE);
if (USART_CheckCommunicationReady(husart) != HAL_OK)
{
husart->global_state = HAL_USART_STATE_IDLE;
return HAL_ERROR;
}
/* Proceed with data transmission IT process starting */
...
return HAL_OK;
}
Within the HAL PPP IRQ handler the global state must move form a step to another
depending of the process flags (in most of the case one single step
HAL_PPP_STATE_{PROCESS#i}_ACTIVE ). When the process is complete (complete
interrupt flag or error interrupt flag is set), the global state must be set back to
HAL_PPP_STATE_IDLE.
HAL_PPP_IRQHandler(hal_ppp_handle_t *hppp)
{
/* Check the global state */
if(STEP1 IT flag)
{
if(hppp->global_state == HAL_PPP_STATE_{PROCESS#i}_{STEP1})
{
...
hppp->global_state = HAL_PPP_STATE_{PROCESS#i}_{STEP#2};
}
}
if(Complete IT flag)
{
if(hppp->global_state == HAL_PPP_STATE_{PROCESS#i}_{STEP#N})
{
...
hppp->global_state = HAL_PPP_STATE_IDLE;
HAL_PPP_Process#iCpltCallback(hal_ppp_handle_t *hppp);
}
}
if(error IT flag)
{
...
hppp->global_state = HAL_PPP_STATE_IDLE;
HAL_PPP_ErrorCallback(hal_ppp_handle_t *hppp);
116

}
}
11.6.2.3. case of Simultaneous parallel processes
When the peripheral allows several processes in parallel (Ex UART Tx/Rx), The global state
machine contains the 3 basic states only: HAL_PPP_STATE_RESET,
HAL_PPP_STATE_INIT and HAL_PPP_STATE_CONFIGURED instead of
HAL_PPP_STATE_IDLE.
Example:
typedef enum
{
/*! Peripheral is not initialized */
HAL_UART_STATE_RESET = 0U,
/*! Peripheral is initialized but not configured */
HAL_UART_STATE_INIT = (1UL << 31U),
/*! Peripheral is initialized and a global config is set */
HAL_UART_STATE_CONFIGURED = (1UL << 30U),
} hal_uart_state_t;
The global state machine is not used for process state transitions. Instead, each process has its
own dedicated state machine that reflects its specific states.
Example:
typedef enum
{
/*! Data Reception process is in reset */
HAL_UART_RX_STATE_RESET = 1U,
/*! Data Reception process is idling */
HAL_UART_RX_STATE_IDLE = (1UL << 31U),
/*! Data Reception process is ongoing */
HAL_UART_RX_STATE_ACTIVE = (1UL << 30U),
/*! Data Reception process is aborting */
HAL_UART_RX_STATE_ABORT = (1UL << 29U),
} hal_uart_rx_state_t;
typedef enum
{
/*! Data Transmission process is in reset */
HAL_UART_TX_STATE_RESET = 1U,
/*! Data Transmission process is idling */
HAL_UART_TX_STATE_IDLE = (1UL << 31U),
/*! Data Transmission process is ongoing */
HAL_UART_TX_STATE_ACTIVE = (1UL << 30U),
/*! Data Transmission process is aborting */
HAL_UART_TX_STATE_ABORT = (1UL << 29U),
} hal_uart_tx_state_t;
The PPP handle provides one state variable per process in addition to the global state
struct hal_uart_handle_s
{
/*! Peripheral instance */
hal_uart_t instance;
/*! USART state information related to global Handle management */
volatile hal_uart_state_t global_state;
/*! USART state information related to Rx operations. */
volatile hal_uart_rx_state_t rx_state;
/*! USART state information related to Tx operations. */
volatile hal_uart_tx_state_t tx_state;
...
}
117

The HAL_PPP_Init function initializes the process states to RESET and the global state
to INIT. These settings are applied at the end of the function, just before returning
hal_status_t HAL_UART_Init(hal_uart_handle_t *huart, hal_uart_t instance)
{
...
huart->rx_state = HAL_UART_RX_STATE_RESET;
huart->tx_state = HAL_UART_TX_STATE_RESET;
huart->global_state = HAL_UART_STATE_INIT;
return HAL_OK;
}
The HAL_PPP_DeInit function reset the process states to RESET and the global state
to RESET. These settings are applied at the end of the function, just before returning
void HAL_UART_DeInit(hal_uart_handle_t *huart)
{
...
/* Reset the states */
huart->global_state = HAL_UART_STATE_RESET;
huart->rx_state = HAL_UART_RX_STATE_RESET;
huart->tx_state = HAL_UART_TX_STATE_RESET;
}
The HAL_PPP_SetConfig function must verify that the global state is either INIT or
CONFIGURED. Additionally, it must ensure that all process states are either IDLE or RESET
before applying a new configuration. Once the configuration is successfully applied, the
process states should be set to IDLE, and the global state should be set to CONFIGURED
right before returning. This ensures that all configuration actions have been completed, and the
configuration is now effective before updating the states.
hal_status_t HAL_UART_SetConfig(hal_uart_handle_t *huart, const hal_uart_config_t *p_config)
{
ASSERT_DBG_PARAM(huart != NULL);
ASSERT_DBG_PARAM(p_config != NULL);
ASSERT_DBG_PARAM(IS_UART_PARITY(p_config->parity));
...
ASSERT_DBG_STATE(huart->global_state, (uint32_t)(HAL_UART_STATE_INIT | HAL_UART_STATE_CONFIGURED));
ASSERT_DBG_STATE(huart->rx_state, (uint32_t)(HAL_UART_RX_STATE_RESET | HAL_UART_RX_STATE_IDLE));
ASSERT_DBG_STATE(huart->tx_state, (uint32_t)(HAL_UART_TX_STATE_RESET | HAL_UART_TX_STATE_IDLE));
...
huart->rx_state = HAL_UART_RX_STATE_IDLE;
huart->tx_state = HAL_UART_TX_STATE_IDLE;
huart->global_state = HAL_UART_STATE_CONFIGURED;
return HAL_OK;
}
A blocking process API must check that the global state is “CONFIGURED”, in addition it
must check that the given process state is also “IDLE” in order to start. The process state must
be then set to various process steps allowing to accomplish the given process (in most of the
case one single step HAL_PPP_STATE_{PROCESS#i}_ACTIVE ). The global state must
remain unchanged (i.e “CONFIGURED”)
118

At the end of the process, the process state must be set back to “IDLE” independently from the
process status (success or error).
hal_status_t HAL_UART_Transmit(hal_uart_handle_t *huart, const void *p_data, uint32_t size_byte,
uint32_t timeout_ms)
{
ASSERT_DBG_PARAM(huart != NULL);
ASSERT_DBG_PARAM(p_data != NULL);
ASSERT_DBG_PARAM(size_byte != 0);
ASSERT_DBG_STATE(huart->global_state, HAL_UART_STATE_CONFIGURED);
ASSERT_DBG_STATE(huart->tx_state, HAL_UART_TX_STATE_IDLE);
HAL_CHECK_UPDATE_STATE(huart, tx_state, HAL_UART_TX_STATE_IDLE, HAL_UART_TX_STATE_ACTIVE);
...
/* check some flags */
if (UART_Checkflags(huart) != HAL_OK)
{
huart->tx_state = HAL_UART_TX_STATE_IDLE;
return HAL_ERROR;
}
...
huart->tx_state = HAL_UART_TX_STATE_IDLE;
return HAL_OK;
}
A non-blocking process API (using Interrupt or DMA) must verify that the global state is
"CONFIGURED". Additionally, it must check that the given process state is also "IDLE"
before starting. The process state is then set to the initial process step (typically a single step,
such as HAL_PPP_STATE_{PROCESS#i}_ACTIVE). The global state should remain
unchanged (i.e., "IDLE").
If an error occurs that prevents the process from starting, the process state must be restored to
"IDLE", and the API should return HAL_ERROR.
hal_status_t HAL_UART_Transmit_IT(hal_uart_handle_t *huart, const void *p_data, uint32_t size_byte)
{
ASSERT_DBG_PARAM(huart != NULL);
ASSERT_DBG_PARAM(p_data != NULL);
ASSERT_DBG_PARAM(size_byte != 0);
ASSERT_DBG_STATE(huart->global_state, HAL_UART_STATE_CONFIGURED);
ASSERT_DBG_STATE(huart->tx_state, HAL_UART_TX_STATE_IDLE);
HAL_CHECK_UPDATE_STATE(huart, tx_state, HAL_UART_TX_STATE_IDLE, HAL_UART_TX_STATE_ACTIVE);
...
/* check some flags */
if (UART_Checkflags(huart) != HAL_OK)
{
huart->tx_state = HAL_UART_TX_STATE_IDLE;
return HAL_ERROR;
}
/* Proceed with data transmission IT process starting */
...
return HAL_OK;
}
119

Within the interrupt handler, the process state should transition from one step to another based
on the process flags (typically a single step, such as
HAL_PPP_STATE_{PROCESS#i}_ACTIVE). When the process is complete (indicated by
the completion interrupt flag or error interrupt flag), the process state should be set back to
HAL_PPP_STATE_IDLE.
HAL_PPP_IRQHandler(hal_ppp_handle_t *hppp, ...)
{
/* Check the global state */
if(STEP1 IT flag)
{
if(hppp->{process#i}_state == HAL_PPP_STATE_{PROCESS#i}_STEP1)
{
...
hppp->{process#i}_state = HAL_PPP_STATE_{PROCESS#i}_STEP2;
}
}
if(process#i Complete IT flag)
{
if(hppp->{process#i}_state == HAL_PPP_STATE_{PROCESS#i}_STEP#N)
{
...
hppp->{process#i}_state = HAL_PPP_STATE_{PROCESS#i}_IDLE;
HAL_PPP_Process#iCpltCallback(hal_ppp_handle_t *hppp);
}
}
if(process#i error IT flag)
{
...
hppp->{process#i}_state = HAL_PPP_STATE_{PROCESS#i}_IDLE;
HAL_PPP_ErrorCallback(hal_ppp_handle_t *hppp);
}
}
Dedicated APIs must be provided to retrieve the process states (in addition to the
HAL_PPP_GetState that return the global state)
Example:
hal_uart_tx_state_t HAL_UART_GetTxState(const hal_uart_handle_t *huart)
{
ASSERT_DBG_PARAM(huart != NULL);
return huart->tx_state;
}
hal_uart_rx_state_t HAL_UART_GetRxState(const hal_uart_handle_t *huart)
{
ASSERT_DBG_PARAM(huart != NULL);
return huart->rx_state;
}
11.6.2.4. sub-instances process management
When the peripheral includes several sub-instance processes (e.g., TIMER channels), the
global state machine contains only three basic states: RESET, INIT, and IDLE.
typedef enum
{
/** Peripheral not yet initialized */
HAL_TIM_STATE_RESET = 0U,
/** Peripheral initialized but not yet configured */
HAL_TIM_STATE_INIT = (1UL << 31U),
/** Peripheral initialized and a global config applied */
HAL_TIM_STATE_IDLE = (1UL << 30U),
/** Counter is running */
120

HAL_TIM_STATE_ACTIVE = (1UL << 29U),
} hal_tim_state_t;
The global state machine is not used for sub-instance process state transitions. Instead, each
sub-instance has its own dedicated state machine that reflects its specific states. These sub-
instance states should account for sub-blocks when available.
typedef enum
{
/** TIM Channel initial state */
HAL_TIM_CHANNEL_STATE_RESET = (1UL << 31U),
/** TIM Channel ready for use as output channel */
HAL_TIM_OC_CHANNEL_STATE_IDLE = (1UL << 30U),
/** An internal process is ongoing on the TIM output channel */
HAL_TIM_OC_CHANNEL_STATE_ACTIVE = (1UL << 29U),
/** TIM Channel ready for use as input channel */
HAL_TIM_IC_CHANNEL_STATE_IDLE = (1UL << 28U),
/** An internal process is ongoing on the TIM input channel */
HAL_TIM_IC_CHANNEL_STATE_ACTIVE = (1UL << 27U),
} hal_tim_channel_state_t;
In the case of a peripheral where several sub-instances can be active in parallel, a table of sub-
instance states is provided within the handle (e.g., TIM channels). When only a single sub-
instance can be active at a time, a single sub-instance state is maintained.
struct hal_tim_handle_s;
typedef struct hal_tim_handle_s hal_tim_handle_t;
struct hal_tim_handle_s
{
/** HAL TIM instance */
hal_tim_t instance;
/** TIM global state */
volatile hal_tim_state_t global_state;
/** TIM channels state array */
volatile hal_tim_channel_state_t channel_states[HAL_TIM_CHANNELS];
...
}
Or in the case where only one sub-instance can be active at a time, a single sub-instance state
field is provided within the handle.
The HAL_PPP_Init function must set the global state to HAL_PPP_STATE_INIT.
Additionally, it must set the sub-instance states to RESET. Same rules apply, the state setting
must be done at the end of the function right before returning.
hal_status_t HAL_TIM_Init(hal_tim_handle_t *htim, hal_tim_t instance)
{
...
/* Reset channels states */
for (uint32_t i = 0; i < HAL_TIM_CHANNELS; ++i)
{
htim->channel_states[i] = HAL_TIM_CHANNEL_STATE_RESET;
}
/* Init global state */
htim->global_state = HAL_TIM_STATE_INIT;
return HAL_OK;
121

}
The HAL_PPP_DeInit must reset all states including global and sub-instances states.
void HAL_TIM_DeInit(hal_tim_handle_t *htim)
{
ASSERT_DBG_PARAM((htim != NULL));
ASSERT_DBG_PARAM(IS_TIM_INSTANCE(p_tim));
tim_t *p_tim = TIM_INSTANCE(htim);
LL_TIM_DisableCounter(p_tim);
LL_TIM_WRITE_REG(p_tim, DIER, 0U);
LL_TIM_WRITE_REG(p_tim, SR, 0U);
/* Reset channels state */
for (uint32_t i = 0; i < HAL_TIM_CHANNELS; ++i)
{
uint32_t ll_channel = ll_tim_channels[i];
LL_TIM_CC_DisableChannel(p_tim, ll_channel);
htim->channel_states[i] = HAL_TIM_CHANNEL_STATE_RESET;
}
htim->global_state = HAL_TIM_STATE_RESET;
}
The HAL_PPP_SetConfig function must verify that the global state is either INIT or IDLE
and that the sub-instances are not ACTIVE before applying a new configuration. Once the
configuration is applied, the global state should be set to HAL_PPP_STATE_IDLE right
before returning (meaning that all required configuration actions are done before setting the
state and returning)
hal_status_t HAL_TIM_SetConfig(hal_tim_handle_t *htim, hal_tim_config_t *p_config)
{
/* Check parameters */
ASSERT_DBG_PARAM((htim != NULL));
ASSERT_DBG_PARAM((p_config != NULL));
ASSERT_DBG_PARAM(IS_TIM_INSTANCE(htim->Instance));
tim_t *p_tim = TIM_INSTANCE(htim);
/* Check the global state */
ASSERT_DBG_STATE(htim->global_state, (uint32_t)HAL_TIM_STATE_INIT |
(uint32_t)HAL_TIM_STATE_IDLE);
/* Check that all channel states are not ACTIVE */
for (uint32_t i = 0; i < HAL_TIM_CHANNELS; ++i)
{
ASSERT_DBG_STATE(htim->channel_states[i], (uint32_t)HAL_TIM_CHANNEL_STATE_RESET |
(uint32_t)HAL_TIM_CHANNEL_STATE_IDLE);
}
...
hppp->global_state = HAL_PPP_STATE_IDLE;
return status;
}
The HAL_TIM_{SUBBLOCK}_SetConfig{sub-instance} API, used to configure a sub-
instance, must verify that the global state is IDLE and that the sub-instance state is either
122

RESET or IDLE before applying a new configuration. Once the sub-instance is configured,
the sub-instance state should be set to IDLE right before returning (meaning all the
configuration steps of the sub-instance are applied before setting the corresponding state to
IDLE and returning) .
hal_status_t HAL_TIM_OC_SetConfigChannel(hal_tim_handle_t *htim,
hal_tim_channel_t channel,
const hal_tim_oc_channel_config_t *p_config)
{
ASSERT_DBG_PARAM((htim != NULL));
ASSERT_DBG_PARAM((p_config != NULL));
tim_t *p_tim = TIM_INSTANCE(htim);
/* Check the channel is supported by the instance */
ASSERT_DBG_PARAM((IS_TIM_OC_CHANNEL(p_tim, channel)));
/* Check channel configuration parameters */
ASSERT_DBG_PARAM(IS_TIM_OC_POLARITY(p_config->polarity));
ASSERT_DBG_PARAM(IS_TIM_OC_IDLE_STATE(p_config->idle_state));
ASSERT_DBG_STATE(htim->global_state, HAL_TIM_STATE_IDLE);
ASSERT_DBG_STATE(htim->channel_states[channel],
(HAL_TIM_CHANNEL_STATE_RESET | TIM_CHANNEL_STATE_IDLE));
/* Set the channel's direction as output (clear bit CCyS),
configure output channel polarity and idle state */
LL_TIM_OC_ConfigOutput(p_tim, ll_tim_channels[channel],
(uint32_t)p_config->polarity | (uint32_t)p_config->idle_state);
htim->channel_states[channel] = HAL_TIM_OC_CHANNEL_STATE_IDLE;
return HAL_OK;
}
The transitions between IDLE and ACTIVE states are typically performed within:
• The dedicated global HAL_PPP_Start/Stop functions
(e.g., HAL_TIM_Start/HAL_TIM_Stop)
• The dedicated sub-instance Start/Stop APIs
(e.g., HAL_TIM_OC_StartChannel/HAL_TIM_OC_StopChannel)
Similarly, the state must be checked using ASSERT within these functions:
In addition to the HAL_PPP_GetState, a function allowing the retrieve the sub-instance state
must be provided:
hal_tim_channel_state_t HAL_TIM_GetChannelState(const hal_tim_handle_t *htim,
hal_tim_channel_t channel)
{
ASSERT_DBG_PARAM((htim != NULL));
ASSERT_DBG_PARAM(IS_TIM_CHANNEL(channel));
return htim->channel_states[channel];
}
11.6.2.5. states transition and validity check
When starting a HAL_PPP_Process, the transition from the IDLE state to the first process step
(or ACTIVE state) must be atomic. A concurrent thread attempting to start the same ongoing
123

HAL_PPP_Process will be rejected, and the HAL_PPP_Process will return HAL_BUSY in
this case.
Note that this protection can be enabled or disabled through the
USE_HAL_CHECK_PROCESS_STATE definition in the HAL configuration file (enabled by
default). Depending on the target Cortex-M architecture, the transition from the IDLE state to
the first process step (or ACTIVE state) must be based on a critical section for ARMv6
architecture or exclusive load/store instructions for ARMv7/ARMv8 architectures.
A macro HAL_CHECK_AND_UPDATE_STATE must be provided within the
stm32tnxx_hal_def.h file to ensure safe state transitions. When the compilation flag
USE_HAL_CHECK_PROCESS_STATE is set to 1:
The HAL_CHECK_AND_UPDATE_STATE macro must be based on critical section
ENTER/EXIT for ARMv6 (Cortex-M0/M0+ based devices).
The HAL_CHECK_AND_UPDATE_STATE macro must be based on exclusive load/store
instructions (__LDREXW/__STREXW) for ARMv7/ARMv8.
When the compilation flag USE_HAL_CHECK_PROCESS_STATE is not defined or set to 0,
the HAL_CHECK_AND_UPDATE_STATE macro must perform a direct update of the state
without any check.
• ARMv7/ARMv8 typical implementation:
/** @brief Check the current peripheral handle state and move it to new state in an atomic way.
* @param handle specifies the Peripheral Handle.
* @param state_field specifies the state field within the Handle.
* @param ppp_conditional_state state to be checked to authorize moving to the new state.
* @param ppp_new_state new state to be set.
* @note This macro can be used for the following purpose:
* - When the define USE_HAL_CHECK_PROCESS_STATE is set to "1", this macro allows to check the current
* handle state versus a conditional state and if true set to the desired new state.
* the check and update of the state is done using exclusive Load/store instruction making
* the operation atomic
* - When the define USE_HAL_CHECK_PROCESS_STATE is not set to "1", this macro simply assign the new
* handle state field to the new desired state without any check
* @retval HAL_BUSY if the define USE_HAL_CHECK_PROCESS_STATE is set to "1" and the current state doesn't match
* ppp_conditional_state.
*/
#if defined(USE_HAL_CHECK_PROCESS_STATE) && (USE_HAL_CHECK_PROCESS_STATE == 1)
#define HAL_CHECK_UPDATE_STATE(handle, state_field, ppp_conditional_state, ppp_new_state) \
do { \
do { \
/* Return HAL_BUSY if the status is not ready */ \
if (__LDREXW((volatile uint32_t *)((uint32_t)&(handle)->state_field)) != (uint32_t)(ppp_conditional_state)) \
{ \
return HAL_BUSY; \
} \
/* if state is ready then attempt to change the state to the new one */ \
} while (__STREXW((uint32_t)(ppp_new_state), (volatile uint32_t *)((uint32_t)&((handle)->state_field))) != 0U); \
/* Do not start any other memory access until memory barrier is complete */ \
__DMB(); \
} while (0)
#else
#define HAL_CHECK_UPDATE_STATE(handle, state_field, ppp_conditional_state, ppp_new_state) \
(handle)->state_field = (ppp_new_state)
#endif /* USE_HAL_CHECK_PROCESS_STATE == 1 */
• ARMv6 typical implementation:
/** @brief Check the current peripheral handle state and move it to new state in an atomic way.
124

* @param handle specifies the Peripheral Handle.
* @param state_field specifies the state field within the Handle.
* @param ppp_conditional_state state to be checked to authorize moving to the new state.
* @param ppp_new_state new state to be set.
* @note This macro can be used for the following purpose:
* - When the define USE_HAL_CHECK_PROCESS_STATE is set to "1", this macro allows to check the current
* handle state versus a conditional state and if true set to the desired new state.
* the check and update of the state is done using exclusive Critical Section making
* the operation atomic
* - When the define USE_HAL_CHECK_PROCESS_STATE is not set to "1", this macro simply assign the new
* handle state field to the new desired state without any check
* @retval HAL_BUSY if the define USE_HAL_CHECK_PROCESS_STATE is set to "1" and the current state doesn't match
* ppp_conditional_state.
*/
#if defined(USE_HAL_CHECK_PROCESS_STATE) && (USE_HAL_CHECK_PROCESS_STATE == 1)
#define HAL_CHECK_UPDATE_STATE(handle, state_field, ppp_conditional_state, ppp_new_state) \
do { \
HAL_ENTER_CRITICAL_SECTION() ; \
/* check the state */ \
if((handle)->state_field != (ppp_conditional_state)) \
{ \
/* Exit critical section */ \
HAL_EXIT_CRITICAL_SECTION(); \
return HAL_BUSY; \
} \
(handle)->state_field = (ppp_new_state); \
/* Exit critical section */ \
HAL_EXIT_CRITICAL_SECTION(); \
} while (0) \
#else
#define HAL_CHECK_UPDATE_STATE(handle, state_field, ppp_conditional_state, ppp_new_state) \
(handle)->state_field =
(ppp_new_state) \
#endif /* USE_HAL_CHECK_PROCESS_STATE == 1 */
The state machine transition from IDLE to the first PROCESS#i state (or ACTIVE) must be
based on a call to HAL_CHECK_AND_UPDATE_STATE as shown below (example for
global state transition):
hal_status_t HAL_TIM_Start(hal_tim_handle_t *htim)
{
ASSERT_DBG_PARAM((htim != NULL));
ASSERT_DBG_STATE(htim->global_state, HAL_TIM_STATE_IDLE);
HAL_CHECK_UPDATE_STATE(htim, global_state, HAL_TIM_STATE_IDLE,
HAL_TIM_STATE_ACTIVE);
tim_t *p_tim = TIM_INSTANCE(htim);
…
LL_TIM_EnableCounter(p_tim);
return HAL_OK;
}
11.6.2.6. Additional rules for states transition
When moving from an ACTIVE state back to IDLE (end of process, process stopped, aborted,
or an error encountered leading to the end of the process), use a direct set of the state to IDLE
without using the HAL_CHECK_AND_UPDATE_STATE macro. The
HAL_CHECK_AND_UPDATE_STATE macro is to be used when starting a process to move
from IDLE to ACTIVE.
Once the state is set to IDLE, there should be no further processing. Depending on the type of
process, the following actions should be taken:
125

• Blocking Process (Polling Process): Return immediately.
• Non-Blocking Process (IT or DMA): Call the completion or error callback, then return
immediately.
11.6.3. Error management
A variable indicating the last occurred errors within processes must be provided within the
HAL PPP handle under the compilation flag “USE_HAL_PPP_GET_LAST_ERRORS” as
follow:
• If a single process can run at a time: one single variable “last_error_codes” holding the
last occurred errors within the last executed process.
• If several processes can run in parallel: one “last_{process#i}_error_codes” per process
must be provided, holding the last occurred errors respectively within the last executed
Process#i
Within a process API:
• At the beginning reset the last_error_codes or last_{process#i}_error_codes variable
(under the compilation flag “USE_HAL_PPP_GET_LAST_ERRORS”)
• When a processing error occurs within the called API:
• in case of an internal error(s) (IP error):
o Store the error codes within the last_error_codes or last_{process#i}_error_codes
variable (under the compilation flag “USE_HAL_PPP_GET_LAST_ERRORS”)
o Return HAL_ERROR this applies for any API: polling API or a non-blocking
IT/DMA API
o Note that the error codes must be provided as bitmapped defines so they can be
ored/combined and stored into last_error_codes or last_{process#i}_error_codes
o User can retrieve the last occurred errors using the API “uint32_t
HAL_PPP_GetLastErrors(hppp)“, This API must be provided under the
compilation flag “USE_HAL_PPP_GET_LAST_ERRORS”
• When an asynchronous error occurs during a non-blocking operation (an error interrupt
occurs)
o The error interrupt must be handled by the IRQ handler.
o The IRQ handler must read in one shot the peripheral flags relative to the
errors.
o If one or several error flags, the variable last_error_codes or
last_{process#i}_error_codes must be updated accordingly (under the
compilation flag “USE_HAL_PPP_GET_LAST_ERRORS”)
o Note that the error codes must be provided as bitmapped defines so they can be
ored/combined and stored into last_error_codes or
last_{process#i}_error_codes
o The error callback is called one time within the IRQ handler (if one or several
errors flags are active)
o The error callback must NOT provide the error code as a parameter, the error
callback is called independently from the compilation flag
“USE_HAL_PPP_GET_LAST_ERRORS
126

User can retrieve the last occurred errors using the API “uint32_t
HAL_PPP_GetLastErrors(hppp)“, This API must be provided under the compilation flag
“USE_HAL_PPP_GET_LAST_ERRORS”.
#if defined (USE_HAL_PPP_REGISTER_CALLBACK) && (USE_HAL_PPP_REGISTER_CALLBACKS == 1)
typedef void (*hal_ppp_cb_t)(hal_ppp_handle_t * hppp); /*!< pointer to a PPP callback function */
#endif /* USE_HAL_PPP_REGISTER_CALLBACKS */
struct hal_ppp_handle_s {
hal_ppp_t instance; /*!< Peripheral instance */
...
#if defined (USE_HAL_PPP_GET_LAST_ERRORS) && (USE_HAL_PPP_GET_LAST_ERRORS == 1)
/* Single process mode: one variable storing the last errors */
volatile uint32_t last_error_codes;
/* Parallel process mode: one variable storing the last errors per process */
volatile uint32_t last_{process#i}_error_codes;
#endif /* USE_HAL_PPP_GET_LAST_ERRORS */
#if defined (USE_HAL_PPP_REGISTER_CALLBACK) && (USE_HAL_PPP_REGISTER_CALLBACKS == 1)
hal_ppp_cb_t p_event_i_cb; /*!< PPP event i callback */
hal_ppp_cb_t p_error_cb; /*!< Error callback */
#endif /* USE_HAL_PPP_REGISTER_CALLBACKS */
};
11.6.3.1. Error codes definition
Error codes must be provided as bit mapped defines listing the possible errors of the given
peripheral.
Error codes must reflect the processes errors only i,e the errors that are relative to the
peripheral process execution and corresponding to HW error flags:
• HAL_PPP_ERROR_INVALID_PARAM must not be defined (removed if existing)
• HAL_PPP_ERROR_INVALID_CALLBACK must not be defined (removed if existing)
• HAL_PPP_ERROR_TIMEOUT must be kept only in case of the peripheral provide a HW
timeout error flag.
• Error codes are provided as bitmapped defines and organized/grouped by:
o Common errors: for processes common errors
o Specific process #i errors (for both cases single process at a time and parallel
processes)
o This allows to combine errors into the last error codes variable(s)
o This allows also to retrieve all last errors combined using “uint32_t
HAL_PPP_GetLastErrors(hppp)“ for both cases single process at a time and
parallel processrs
#if defined (USE_HAL_PPP_GET_LAST_ERRORS) && (USE_HAL_PPP_GET_LAST_ERRORS == 1)
#define HAL_PPP_ERROR_NONE (0UL) /*!< No error */
/* Common errors */
#define HAL_PPP_ERROR_ERRx (0x01UL << 0) /*!< Error x: common to all processes */
...
#define HAL_PPP_ERROR_ERRy (0x01UL << 7U) /*!< Error y: common to all processes */
...
/* Process-specific errors */
#define HAL_PPP_{PROCESS#i}_ERROR_ERRm (0x01UL << 8U) /*!< Process#i specific Error m */
...
#define HAL_PPP_{PROCESS#i}_ERROR_ERRn (0x01UL << 15U) /*!< Process#i specific Error n */
#define HAL_PPP_{PROCESS#j}_ERROR_ERRk (0x01UL << 16U) /*!< Process#j specific Error k */
...
127

#define HAL_PPP_{PROCESS#j}_ERROR_ERRl (0x01UL << 24U) /*!< Process#j specific Error l */
#endif /* USE_HAL_PPP_GET_LAST_ERRORS */
Note: if there is a fatal error that requires a recovery sequence in the application code then a
dedicated error code define must be provided ( HAL_PPP_FAULT_ERROR_XXX) in
addition to the dedicated HAL_PPP_STATE_FAULT described in the “State machine”
section.
11.6.3.2. Error codes initialization
The last_error_codes handle field must be reset during HAL_PPP_Init. In the case of a single
process at a time, the last_error_codes must be reset at the beginning of all process APIs
(Polling, IT, and DMA). In the case of several processes running in parallel, each process#i
API (Polling, IT, and DMA) must reset (at the beginning) the corresponding
last_{process#i}_error_codes.
Note: A new initialization and configuration sequence is required to reuse the handle object.
Therefore, it is not necessary/requested to clean other internal fields within the HAL PPP
handle during HAL_PPP_DeInit, as this clean-up is already performed in HAL_PPP_Init. This
applies also for the last_error_codes or last_{process#i}_error_codes variable that are not
cleaned within the HAL_PPP_DeInit.
hal_status_t HAL_PPP_Init(hal_ppp_handle_t *hppp, hal_ppp_t instance) {
...
#if defined (USE_HAL_PPP_GET_LAST_ERRORS) && (USE_HAL_PPP_GET_LAST_ERRORS == 1)
/* Single process mode: reset the last error codes */
hppp->last_error_codes = HAL_PPP_ERROR_NONE;
/* Parallel process mode: reset the last error codes for each process */
hppp->last_{process#i}_error_codes = HAL_PPP_ERROR_NONE;
...
hppp->last_{process#j}_error_codes = HAL_PPP_ERROR_NONE;
#endif /* USE_HAL_PPP_GET_LAST_ERRORS */
/* Init the global state */
hppp->global_state = HAL_PPP_STATE_INIT;
return HAL_OK;
}
11.6.3.3. HAL_PPP_GetLastErrorCodes API:
A “HAL_PPP_GetLastErrorCodes” API must be provided as bellow:
• Case of single process at a time:
#if defined (USE_HAL_PPP_GET_LAST_ERRORS) && (USE_HAL_PPP_GET_LAST_ERRORS == 1)
uint32_t HAL_PPP_GetLastErrorCodes(const hal_ppp_handle_t *hppp)
{
return hppp->last_error_codes;
}
#endif /* USE_HAL_PPP_GET_LAST_ERRORS */
• Case of several processes can run in parallel:
#if defined (USE_HAL_PPP_GET_LAST_ERRORS) && (USE_HAL_PPP_GET_LAST_ERRORS == 1)
uint32_t HAL_PPP_GetLastErrorCodes(const hal_ppp_handle_t *hppp)
{
uint32_t tmp = last_{process#i}_error_codes;
return (last_{process#j}_error_codes | tmp);
}
128

#endif /* USE_HAL_PPP_GET_LAST_ERRORS */
11.6.3.4. Error management within a polling-based process
In the error management of a polling-based process, the last_error_codes should be reset at the
beginning when the compilation flag USE_HAL_PPP_GET_LAST_ERRORS is defined.
Throughout the process, peripheral error flags are periodically checked to monitor progress. If
the compilation flag USE_HAL_PPP_GET_LAST_ERRORS is defined, any corresponding
error codes are accumulated into last_error_codes. In the event of a blocking error, the process
must immediately stop, and the API must return HAL_ERROR. For non-blocking errors, the
process continues, and the API will return HAL_ERROR once the process concludes. If no
errors are encountered, the API will return HAL_OK. When the API returns HAL_ERROR,
users can retrieve the accumulated error codes by calling the HAL_PPP_GetLastErrorCodes
API.
hal_status_t HAL_PPP_Process#i(hal_ppp_handle_t *hppp, ...)
{
uint32_t error_flags;
hal_status_t status = HAL_OK;
#if defined (USE_HAL_PPP_GET_LAST_ERRORS) && (USE_HAL_PPP_GET_LAST_ERRORS == 1)
/* in case of single process at a time: one single variable storing the last errors */
hppp->last_error_codes = HAL_PPP_ERROR_NONE;
#endif /* USE_HAL_PPP_GET_LAST_ERRORS */
...
error_flags = LL_ReadErrorFlags ((PPP_TypeDef *)hppp—>instance, ...);
#if defined (USE_HAL_PPP_GET_LAST_ERRORS) && (USE_HAL_PPP_GET_LAST_ERRORS == 1)
if(common error flag X in error_flags)
{
hppp->last_error_codes |= HAL_PPP_ERROR_ERRx;
}
..
if(process #i error flag m in error_flags)
{
hppp->last_error_codes |= HAL_PPP_{PROCESS#i}_ERROR_ERRm;
}
#endif /* USE_HAL_PPP_GET_LAST_ERRORS */
...
if(error_flags) status = HAL_ERROR;
return status;
}
11.6.3.5. Error management within an Interrupt based process
Similar to the polling process, if an error occurs within the HAL_PPP_Process_IT, the error
codes are updated under the compilation flag USE_HAL_PPP_GET_LAST_ERRORS, and
the API returns HAL_ERROR.
If an error occurs after starting the interrupt (IT) process, the PPP HAL IRQ handler must
intercept the errors interrupt(s), check and clear the error flags and disable the error
interrupt(s) as usual. The error code is updated and accumulated under the compilation flag
USE_HAL_PPP_GET_LAST_ERRORS, and the error callback must be issued by the IRQ
handler once all error flags have been checked and error codes accumulated.
129

11.6.3.6. Error management within a DMA based process
Within the HAL_PPP_Process_DMA API, the corresponding DMA complete and error
callbacks must be set to dedicated internal callbacks implemented within the PPP HAL
driver's "c" file itself, specifically PPP_DMAProcessCplt and PPP_DMAError.
hal_status_t HAL_PPP_Process_DMA(hal_ppp_handle_t *hppp, const void *p_data, uint32_t size_byte)
{
...
/* Set the PPP DMA transfer complete callback */
hppp->hdma_#i->p_xfer_cplt_cb = PPP_DMAProcessCplt;
/* Set the PPP DMA Half transfer complete callback */
hppp->hdma_#i->p_xfer_halfcplt_cb = PPP_DMAProcessHalfCplt;
/* Set the DMA error callback */
hppp->hdma_#i->p_xfer_error_cb = PPP_DMAError;
...
}
When a processing error occurs within the HAL_PPP_Process_DMA API, it must return
HAL_ERROR. If no error is detected, the HAL_PPP_Process_DMA must proceed to start the
DMA. If the DMA is not started correctly, meaning the HAL DMA Start API does not return
HAL_OK, the HAL_PPP_Process_DMA API must return HAL_ERROR. Otherwise,
HAL_PPP_Process_DMA must enable the peripheral DMA request, start the DMA transfer
and return HAL_OK, indicating that the process has started successfully.
If a DMA transfer error occurs after starting the DMA process, the DMA error callback
(implemented within the HAL PPP driver) must update the parent peripheral error codes under
the compilation flag “USE_HAL_PPP_GET_LAST_ERRORS” and call the parent peripheral
error callback.
static void PPP_DMA_Error(hal_dma_handle_t *hdma)
{
hal_ppp_handle_t *hppp = (hal_ppp_handle_t *)(hdma->Parent);
#if defined (USE_HAL_PPP_GET_LAST_ERRORS) && (USE_HAL_PPP_GET_LAST_ERRORS == 1)
/* in case of single process at a time: one single variable storing the last errors */
hppp->last_error_codes |= HAL_PPP_{PROCESS#i}_ERROR_DMA;
/* in in case of several processes that can be active in parallel:
one variable storing the last errors per process */
hppp->last_{process#i}_error_codes |= HAL_PPP_{PROCESS#i}_ERROR_DMA;
#endif /* USE_HAL_PPP_GET_LAST_ERRORS */
...
#if (USE_HAL_PPP_REGISTER_CALLBACKS == 1)
/*Call registered error callback*/
ph_ppp->ErrorCallback(hppp);
#else
/*Call legacy weak error callback*/
HAL_PPP_ErrorCallback(hppp);
#endif /* USE_HAL_PPP_REGISTER_CALLBACKS */
}
#endif /* (USE_HAL_PPP_DMA) && (USE_HAL_PPP_DMA == 1) */
11.6.3.7. Error Callback
The weak error callback (default) and the error callback registration API must be provided as
follow:
130

#if defined (USE_HAL_PPP_REGISTER_CALLBACK) && (USE_HAL_PPP_REGISTER_CALLBACKS == 1)
…
hal_status_t HAL_PPP_RegisterErrorCallback (hal_ppp_handle_t *hppp,
hal_ppp_cb_t p_callback);
#endif
/**
* @brief PPP error callback.
* @param hppp PPP handle.
* @retval None
*/
__WEAK void HAL_PPP_ErrorCallback(hal_ppp_handle_t *hppp)
{
/* Prevent unused argument(s) compilation warning */
UNUSED(hppp);
/* @warning : This function should not be modified, when the callback is needed,
the HAL_PPP_ErrorCallback can be implemented in the user file.
*/
}
#if defined (USE_HAL_PPP_REGISTER_CALLBACK) && (USE_HAL_PPP_REGISTER_CALLBACKS == 1)
/**
* @brief Register the PPP error Callback
* To be used instead of the weak HAL_PPP_ErrorCallback() predefined default callback
* @param hppp Pointer to a hal_ppp_handle_t structure
* @param pCallback pointer to the Error Callback function
* @retval HAL_OK if success
* @retval HAL_INVALID_PARAM when the p_callback is NULL
*/
hal_status_t HAL_PPP_RegisterErrorCallback(hal_ppp_handle_t *hppp, hal_ppp_error_cb_t p_callback)
{
ASSERT_DBG_PARAM((hppp != NULL));
ASSERT_DBG_PARAM((p_callback != NULL));
#if defined(USE_HAL_CHECK_PARAM)
/* check the pCallback pointer */
if(p_callback == NULL)
{
return HAL_INVALID_PARAM;
}
#endif /* USE_HAL_CHECK_PARAM */
hppp->p_error_cb = p_callback;
return HAL_OK;
}
#endif
11.6.4. status and return
The HAL status enumeration must be used to return the HAL API status when applicable. This
enumeration must be defined in the “stm32tnxx_hal_def.h” with five possible values as
following:
typedef enum
{
HAL_OK = 0x00000000U, /* HAL operation completed successfully */
HAL_ERROR = 0xFFFFFFFFU, /* HAL operation completed with error */
HAL_BUSY = 0x55555555U, /* HAL concurrent process ongoing */
HAL_INVALID_PARAM = 0xAAAAAAAAU, /* HAL invalid parameter */
HAL_TIMEOUT = 0x5A5A5A5AU /* HAL operation exceeds user timeout */
} hal_status_t;
131

• HAL_ERROR is returned in case of an internal error, including exceeding an intrinsic
hardware timeout.
• HAL_INVALID_PARAM is returned in case of an invalid parameter that can lead to
a hard fault or a memory exception (e.g., null pointer).
• HAL_BUSY is returned when trying to start a process while a concurrent one is
ongoing.
• HAL_TIMEOUT is used exclusively when the operation exceeds the user-defined
timeout (e.g., Polling API with user timeout as a parameter).
Note: The values of the hal_status_t enumeration are set to have a minimum Hamming
distance of at least 8 for function return values. This is to ensure compliance with the secure
coding rule: "Return value of sensitive function must have a Hamming distance of at least 8."
for more details refer to the secure coding rules [10].
Secure coding rules must be applied to the following cryptography IP drivers: CRC,
AES/CRYP, HASH, RNG, PKA, and OTFDEC/MCE. Since the hal_status_t enumeration is
used by all HAL drivers, including the crypto drivers, the secure coding rule requiring a
Hamming distance of at least 8 must be applied to this enumeration.
The HAL APIs must check the input parameters using dedicated assertions. However, pointer
parameters are critical and may lead to a hard fault if they are NULL. These parameters must
be checked at runtime within the first API that deals with the given parameter:
• When the runtime parameter check fails, the API must return
HAL_INVALID_PARAM.
• The runtime check must be implemented under #if defined
(USE_HAL_CHECK_PARAM).
• The HAL_PPP_Init function must check the handle pointer at runtime (as it is the first
API dealing with the handle).
hal_status_t HAL_PPP_Init(hal_ppp_handle_t *hppp, hal_ppp_t instance)
{
/* Check the PPP handle allocation */
ASSERT_DBG_PARAM(hppp != NULL);
#if defined(USE_HAL_CHECK_PARAM) && (USE_HAL_CHECK_PARAM == 1U)
/* check the handle struct pointer */
If (hppp == NULL)
{
return HAL_INVALID_PARAM;
}
#endif /* USE_HAL_CHECK_PARAM */
...
}
• The global configuration API, HAL_PPP_SetConfig, must check the configuration
structure pointer at runtime. However, it must not check the handle, as this was already
verified during HAL_PPP_Init.
hal_status_t HAL_PPP_SetConfig(hal_ppp_handle_t *hppp, hal_ppp_config_t *p_config)
{
uint32_t tickstart; /*Only when need to wait on flag for a delayed configuration */
/* Check the PPP handle & config allocation */
ASSERT_DBG_PARAM(hppp != NULL);
ASSERT_DBG_PARAM(p_config != NULL);
#if defined(USE_HAL_CHECK_PARAM) && (USE_HAL_CHECK_PARAM == 1U)
/* check the config struct pointer */
if (p_config == NULL)
{
return HAL_INVALID_PARAM;
}
132

#endif /* USE_HAL_CHECK_PARAM */
...
}
• The sub-block configuration
API, HAL_PPP_{SUBBLOCK}_SetConfig{Subinstance}, must check the
configuration structure pointer at runtime. However, it must not check the handle, as
this was already verified during HAL_PPP_Init.
• The HAL_PPP_Process API must check the p_data pointer at runtime to ensure it is
not NULL. However, it must not check the handle, as this was already verified
during HAL_PPP_Init.
hal_status_t HAL_PPP_Process(hal_ppp_handle_t *hppp, const void *p_data, uint32_t size, ...)
{
uint32_t tick_start;
const uintxx_t *pdata_xx = (const uintxx_t *)p_data; // for MISRA compliancy, xx = 8, 16, 32
/* Check the PPP handle & cparameters */
ASSERT_DBG_PARAM(hppp != NULL);
ASSERT_DBG_PARAM(p_data != NULL);
ASSERT_DBG_PARAM(size != 0);
/* In case single process can run at a time: Check the global state */
ASSERT_DBG_STATE(hppp->global_state == HAL_PPP_STATE_IDLE);
#if defined(USE_HAL_CHECK_PARAM) && (USE_HAL_CHECK_PARAM == 1)
/* check p_data pointer and data size */
if((p_data == NULL) || (size == 0))
{
return HAL_INVALID_PARAM;
}
#endif /* USE_HAL_CHECK_PARAM */
...
}
All HAL APIs must return a hal_status_t.
• Initialization: HAL_PPP_Init
• Configuration: HAL_PPP_SetConfig, HAL_PPP_{SUBBLOCK}_SetConfig{subinst
ance}
• Unitary
APIs: HAL_PPP_SetItem, HAL_PPP_{SUBBLOCK}_Set{Subinstance}Item
• Features: HAL_PPP_Set{Feature}, HAL_PPP_SetConfig{Feature}, HAL_PPP_Enab
le{Feature}, HAL_PPP_Disable{Feature}
• Process
APIs: HAL_PPP_Process, HAL_PPP_Start, HAL_PPP_Stop, HAL_PPP_Abort, HAL
_PPP_Pause, HAL_PPP_Resume, etc.
133

Any HAL PPP action API (e.g., configuration, processing, enabling, disabling) must return
a hal_status_t type. The hal_status_t return type is used universally across all HAL action
services, not just for drivers that have a state machine or/and a handle.
When there are no checks inside the API, it should simply return HAL_OK. In cases where
checks are performed, the API should return HAL_OK for success, or HAL_ERROR,
HAL_BUSY, HAL_TIMEOUT, or HAL_INVALID_PARAM according to the specific
scenario.
The rationale behind this approach is to ensure portability across different STM32 series. By
providing HAL APIs with a hal_status_t return type, we can accommodate the varying
hardware peripherals implementations across different series. For example, a particular action
might require checking a particular flag on one STM32 series but not on another.
11.6.4.1. HAL_PPP_GetXXX APIs (Informative APIs):
• Getting a configuration: In this case the API return is avoid and the configuration is
provided by reference
• Direct Return: In cases where the API directly returns a value, it must return an enum
or a uint32_t type.
• Procedural APIs: If the API involves a procedure that may fail, it must return a
hal_status_t.
• Applicability: This applies exclusively to pure informative APIs, which simply read
register fields and return information.
Examples:
• Getting a configuration:
void HAL_UART_GetConfig(const hal_uart_handle_t *huart, hal_uart_config_t *p_config);
void HAL_TIM_BREAK_GetConfigInput(const hal_tim_handle_t *htim,
hal_tim_break_input_id_t brkin,
hal_tim_break_input_config_t *p_config);
• Getting an item without procedural checks:
hal_uart_word_length_t HAL_UART_GetWordLength(const hal_uart_handle_t *huart);
uint32_t HAL_UART_GetBaudRate(const hal_uart_handle_t *huart);
• Getting an item with procedural checks:
hal_status_t HAL_SD_GetCardStatus(hal_sd_handle_t *hsd, hal_sd_card_status_t *p_status);
• Other APIs:
o HAL_PPP_DeInit, HAL_PPP_ResetConfig (when available),
and HAL_PPP_SetUserData APIs must be void.
o HAL_PPP Callbacks and the HAL_PPP_IRQHandler must be void.
o HAL_PPP IT and flag management APIs must be void (note that these APIs
are available only when there is no LL driver):
▪ HAL_PPP_EnableIT
▪ HAL_PPP_DisableIT
▪ HAL_PPP_ClearFlag
134

For System peripherals (GPIO, SYSCFG/SBS, PWR, RCC), the return hal_status_t return
must be used only when needed (internal check). The rationale is that system IPs may differ
significantly across series, and prototype consistency between series is not mandatory.
Private functions are not concerned by this hal_status_t return rule; only the public APIs are
concerned.
11.6.4.2. Secure coding rules considerations:
The secure coding rules are specifically applicable to the cryptography HAL drivers, which
include CRC, AES/CRYP, HASH, RNG, PKA, and OTFDEC/MCE. Most of these secure
coding rules are straightforward coding guidelines. However, there are two rules with
significant architectural impacts:
1. SRC1.6: Return value of sensitive function must have a Hamming distance of at
least 8
Impact: The values of the hal_status_t used as return values must have a Hamming
distance of at least 8 to ensure secure coding practices.
2. SCR1.8: Input parameters must be verified for all sensitive functions (even if not
exported)
Impact: A dedicated define USE_HAL_SECURE_CHECK_PARAM is used to enable
checking the input parameters, in addition to USE_HAL_CHECK_PARAM. This
define is utilized by the HAL drivers for CRC, AES/CRYP, HASH, RNG, PKA, and
OTFDEC/MCE, where compliance with secure coding rules is required. The goal is
that when the define USE_HAL_SECURE_CHECK_PARAM is set to “1”, all the API
inputs parameters are checked.
hal_status_t HAL_PPP_Process(hal_ppp_handle_t*hppp,const void *p_data, uint32_t size_byte, uint32_t
timeout_ms)
{
ASSERT_DBG_PARAM ((hppp!=NULL));
ASSERT_DBG_PARAM ((p_data!=NULL));
ASSERT_DBG_PARAM((size_byte!=0));
ASSERT_DBG_STATE(hppp->global_state,HAL_PPP_STATE_IDLE);
#if (defined(USE_HAL_CHECK_PARAM) &&(USE_HAL_CHECK_PARAM == 1)) \
|| (defined(USE_HAL_SECURE_CHECK_PARAM) &&(USE_HAL_SECURE_CHECK_PARAM == 1))
/*checkpDatapointer and data size*/
if((p_data==NULL) || (size_byte == 0U))
{
return HAL_INVALID_PARAM;
}
#endif /* USE_HAL_CHECK_PARAM */
#if defined(USE_HAL_SECURE_CHECK_PARAM) &&(USE_HAL_SECURE_CHECK_PARAM == 1)
if((hppp ==NULL) || (timeout == 0U))
{
return HAL_INVALID_PARAM;
}
#endif /* USE_HAL_CHECK_PARAM */
...
}
135

11.6.5. HAL buses Acquire/Release mechanism
In HAL1 drivers, an internal HAL LOCK mechanism was provided to protect a standalone
HAL_PPP_Process while it is running, preventing another call from corrupting the ongoing
operation. This HAL lock mechanism was not intended to protect the peripheral handle from
being used by several modules simultaneously. It was only a lock during a standalone
independent process. Additionally, in HAL1 drivers, the HAL LOCK was provided in the
BareMetal version only. No OS version was available, making it impossible to pend a thread
requesting a given HAL PPP process on a given instance while this process was ongoing by
another thread on the same instance.
High-level applicative layers such as BSP IO interfaces, MW interfaces, and user applications
require protection for a sequence of HAL PPP calls against multi-threading. This means the
applicative module must "acquire" the HAL PPP resource, perform the necessary sequence of
HAL PPP API calls to ensure the needed applicative functionality, and then "release" the HAL
PPP resource.
In OS-based applications, it is necessary to “acquire” the full HAL PPP handle to ensure an
applicative sequence. During the applicative sequence, the HAL PPP handle should be
“owned” by a given task, and other tasks should wait until the given sequence is finished. Any
other task trying to launch any HAL operation on the given HAL PPP handle should wait.
Example usage:
HAL_PPP_AcquireBus(hppp)
HAL_PPP_Transmit(hppp, ...)
HAL_PPP_Receive(hppp, ...)
...
HAL_PPP_Transmit(hppp, ...)
...
HAL_PPP_ReleaseBus(hppp)
HAL_PPP_AcquireBus(hppp)
HAL_PPP_Receive_IT(hppp, ...)
...
/* wait for Rx Cplt callback */
HAL_PPP_ReleaseBus(hppp)
HAL_PPP_AcquireBus(hppp)
HAL_PPP_Transmit_IT(hppp, ...)
...
/* wait for Tx Cplt callback */
HAL_PPP_ReleaseBus(hppp)
to meet these requirements, the HAL internal lock mechanism from HAL1 must be removed
and replaced by two APIs per HAL PPP
driver: HAL_PPP_AcquireBus and HAL_PPP_ReleaseBus. These APIs are necessary for bus
peripherals such as I2C, USART, UART, SPI, SAI, I2S, PSSI, CAN/FDCAN, and I3C.
The HAL Acquire/Release APIs must be based on a HAL OS Abstraction Layer (OSAL)
composed of stm32_hal_os.c/.h.
In HAL2, the HAL lock mechanism must be completely removed
(i.e., HAL_LOCK/HAL_UNLOCK must be removed from stm32tnxx_hal_def.h and their
usage in stm32tnxx_hal_ppp.c).
Additionally, HAL_PPP_AcquireBus and HAL_PPP_ReleaseBus APIs must be provided for
bus-like peripherals.
136

The Acquire/Release services must be based on a HAL OSAL that provides basic services for
semaphores and mutexes (creation, deletion, acquire, and release). A semaphore parameter is
included in the HAL PPP handle, defined as hal_os_semaphore_t, and conditioned with the
define USE_HAL_MUTEX that must be set to 1 within the HAL configuration
file stm32tnxx_hal_conf.h when needed.
Implementation
• Within the HAL PPP handle: Provide a dedicated semaphore field using the HAL
OSAL semaphore type
/**
* @brief HAL PPP handle Structure definition
*/
struct hal_ppp_handle_s;
typedef struct hal_ppp_handle_s hal_ppp_handle_t;
struct hal_ppp_handle_s
{
hal_ppp_t instance; /*!< HAL Peripheral instance */
...
#if defined(USE_HAL_MUTEX) && (USE_HAL_MUTEX == 1)
hal_os_semaphore_t semaphore; /*!< PPP OS semaphore */
#endif /* USE_HAL_MUTEX */
};
• Within the HAL_PPP_Init:
The HAL_PPP_Init function must create the corresponding OS semaphore by calling
HAL_OS_SemaphoreCreate and storing the result in the handle->semaphore
parameter. The semaphore creation is conditioned with the define
USE_HAL_MUTEX.
hal_status_t HAL_PPP_Init(hal_ppp_handle_t *hppp, hal_ppp_t instance)
{
/* Check the PPP handle allocation */
ASSERT_DBG_PARAM((hppp != NULL));
/* Check the PPP instance */
ASSERT_DBG_PARAM(IS_PPP_INSTANCE((PPP_TypeDef *) ((uint32_t)instance));
#if defined(USE_HAL_CHECK_PARAM)
/* Check the handle struct pointer */
if (hppp == NULL)
{
return HAL_INVALID_PARAM;
}
#endif /* USE_HAL_CHECK_PARAM */
...
#if defined(USE_HAL_MUTEX) && (USE_HAL_MUTEX == 1)
/* Create the PPP semaphore */
if (HAL_OS_SemaphoreCreate(&hppp->semaphore) != HAL_OS_OK)
{
return HAL_ERROR;
}
#endif /* USE_HAL_MUTEX */
...
}
• Within the HAL_PPP_DeInit:
137

The HAL_PPP_DeInit function frees the semaphore by
calling HAL_OS_SemaphoreDelete.
void HAL_PPP_DeInit(hal_ppp_handle_t *hppp)
{
/* Check the PPP handle allocation */
ASSERT_DBG_PARAM((hppp != NULL));
...
#if defined(USE_HAL_MUTEX) && (USE_HAL_MUTEX == 1)
/* Delete the PPP semaphore */
(void)(HAL_OS_SemaphoreDelete(&hppp->semaphore) != HAL_OS_OK);
#endif /* USE_HAL_MUTEX */
...
}
• HAL_PPP_AcquireBus:
The HAL_PPP_AcquireBus function must take the semaphore by calling
HAL_OS_SemaphoreTake.
#if defined(USE_HAL_MUTEX) && (USE_HAL_MUTEX == 1)
hal_status_t HAL_PPP_AcquireBus(hal_ppp_handle_t *hppp, uint32_t timeout)
{
hal_status_t status = HAL_TIMEOUT;
/* Check the PPP handle allocation */
ASSERT_DBG_PARAM(hppp != NULL);
if (HAL_OS_SemaphoreTake(&hppp->semaphore, timeout) == HAL_OS_OK)
{
status = HAL_OK;
}
return status;
}
#endif /* USE_HAL_MUTEX */
• HAL_PPP_ReleaseBus:
The HAL_PPP_ReleaseBus function releases the semaphore by calling
HAL_OS_SemaphoreRelease.
#if defined(USE_HAL_MUTEX) && (USE_HAL_MUTEX == 1)
hal_status_t HAL_PPP_ReleaseBus(hal_ppp_handle_t *hppp)
{
hal_status_t status = HAL_ERROR;
/* Check the PPP handle allocation */
ASSERT_DBG_PARAM(hppp != NULL);
if (HAL_OS_SemaphoreRelease(&hppp->semaphore) == HAL_OS_OK)
{
status = HAL_OK;
}
return status;
}
#endif /* USE_HAL_MUTEX */
11.7. HAL RCC Clock management
The HAL RCC services should be provided in blocks corresponding to different parts of the
clock tree. These services should be encapsulated in APIs with a clear and limited scope
specific to each block and the action to be performed on the given block. For example, an
oscillator such as MSI or HSI is considered a block, and the PLL is another block.
138

This modular approach avoids monolithic functions that configure multiple parts of the clock
tree, which can lead to a significant footprint in the user application. Instead, the user
application should rely on a sequence of these modular services to configure the clock tree
according to its needs. Using STM32CubeMX2 for code generation simplifies this task for the
user by providing a graphical representation of the clock tree and generating the required
sequence based on these scope-limited APIs. This method also ensures an optimized footprint
by only including the necessary configurations.
11.7.1. Oscillators enabling and control services
The HAL RCC driver must provide a set of services to configure and activate different
oscillators. These services allow users to enable, disable, and check the status of various
oscillators such as HSI, MSI, MSIK etc...
Example:
API Description
HAL_RCC_HSI_Enable(); Enable the HSI oscillator
HAL_RCC_HSI_Disable(); Disable the HSI oscillator
hal_rcc_osc_enable_status_t HAL_RCC_HSI_IsEnabled(); Check if the HSI oscillator is enabled
hal_rcc_osc_ready_status_t HAL_RCC_HSI_IsReady(); Check if the HSI oscillator is ready
HAL_RCC_HSI_SetTrimming(); Set the HSI trimming value
HAL_RCC_HSI_GetTrimming(); Get the HSI trimming value
HAL_RCC_HSI_GetCalibration(); Get the HSI calibration value
HAL_RCC_HSI_EnableInStopMode() Enable the HSI oscillator in stop mode
HAL_RCC_HSI_DisableInStopMode(); Disable the HSI oscillator in stop mode
hal_rcc_osc_stop_mode_status_t HAL_RCC_HSI_IsEnabledInStopMode(); Check if the HSI oscillator is enabled in stop mode
Note: The system/SoC related IPs can have different APIs between series if the features are
different (e.g., Cortex, PWR, SYSCFG, RCC). If the feature or a parameter is the same, the
naming should be kept consistent. The number and list of parameters can change if the given
series features are different. If the features are the same, the API naming should remain
consistent. Example:
• HAL_RCC_LSI_Enable (void) on Series X
• HAL_RCC_LSI_Enable (uint32_t divider) on Series Y
Both of the above APIs have the same scope (enabling the LSI), but on Series X, there is no
divider, so no parameter is needed. On Series Y, the LSI requires a divider, so the API
includes a parameter.
11.7.2. PLL configuration and control services
The HAL RCC driver must provide a set of services to configure and control each PLL (for
instance PLL1).
139

For example, the following table lists the APIs provided to configure and control PLL1
(equivalent services must be provided to PLL2/PLL3 or PLL_SAI if available on the given
series:
PLL1 might be used for the system clock and is configured and enabled using
HAL_RCC_PLL1_SetConfig() and HAL_RCC_PLL1_Enable(), respectively. These functions
allow for independent control of the configuration and activation of PLL1.
API Description
hal_status_t HAL_RCC_PLL1_SetConfig(const hal_rcc_pll_config_t *p_config); Configure PLL1
hal_status_t HAL_RCC_PLL1_Enable(void); Enable PLL1
hal_status_t HAL_RCC_PLL1_Disable(void); Disable PLL1
hal_status_t HAL_RCC_PLL1_EnableOutput(uint32_t output); Enable PLL1 output
hal_status_t HAL_RCC_PLL1_DisableOutput(uint32_t output); Disable PLL1 output
hal_status_t HAL_RCC_PLL1_Reset(void); Reset PLL1
void HAL_RCC_PLL1_GetConfig(hal_rcc_pll_config_t *p_config); Get PLL1 configuration
uint32_t HAL_RCC_PLL1_GetOutput(void); Get PLL1 output
hal_rcc_pll_status_t HAL_RCC_PLL1_IsReady(void); Check if PLL1 is ready
void HAL_RCC_PLL1_GetClockFreq(hal_rcc_pll_output_freq_t *p_clk); Get PLL1 clock frequency
hal_status_t HAL_RCC_PLL1_SetFRACN(uint16_t fracn); Set PLL1 fractional part
uint16_t HAL_RCC_PLL1_GetFRACN(void); Get PLL1 fractional part
Th following sequence gives an example of the configuration and activation of the PLL1
knowing that in this scenario, the HSI oscillator is used as source for this PLL:
/* HSI enabling*/
HAL_RCC_HSI_Enable();
/* HSI calibration: optional */
HAL_RCC_HSI_SetTrimmingConfig(HAL_RCC_HSICALIBRATION_DEFAULT);
/* PLL Configuration */
hal_rcc_pll_config_t config_pll;
config_pll.pll_source = HAL_RCC_PLL_SRC_HSI;
config_pll.pll_m = 4;
config_pll.pll_n = 75;
config_pll.pll_p = 2;
config_pll.pll_q = 2;
config_pll.pll_r = 2;
...
HAL_RCC_PLL1_SetConfig(&config_pll);
/* PLL enabling */
HAL_RCC_PLL1_Enable();
/* PLL output enabling */
HAL_RCC_PLL1_EnableOutput(HAL_RCC_PLL1_SYSCLK);
11.7.3. System Clock Source Selection APIs
The HAL RCC driver must provide a set of services to configure and retrieve the system clock
source. These functions allow users to set and get the clock source for the system clock.
140

API Description
HAL_RCC_SetSYSCLKSource (hal_rcc_sysclk_src_t source); Set the system clock source
hal_rcc_sysclk_src_t HAL_RCC_GetSYSCLKSource(void); Get the system clock source
uint32_t HAL_RCC_GetSYSCLKFreq(void); Get the system clock frequency
11.7.4. Busses Prescalers Configuration APIs
The HAL RCC driver must provide a set of services to configure the bus prescalers and
retrieve bus clock frequencies (HCLK and PCLKx). These functions allow users to configure
the prescalers for various buses independently.
There are two set of functions with two abstraction scope to configures the busses prescalers
• Busses presclaers global configuration APIs: HAL_RCC_SetBusClockConfig and
HAL_RCC_GetBusClockConfig are used to configure and retrieve the configuration
of all bus prescalers at once. These functions take a structure containing all the
prescaler settings, allowing for a comprehensive configuration in a single call.
hal_rcc_bus_clk_divider_t config_bus;
config_bus.ahb_clk_divider = HAL_RCC_HCLK_DIV1;
config_bus.apb1_clk_divider = HAL_RCC_PCLK_DIV1;
config_bus.apb2_clk_divider = HAL_RCC_PCLK_DIV1;
config_bus.apb3_clk_divider = HAL_RCC_PCLK_DIV1;
HAL_RCC_SetBusClockConfig(&config_bus);
API Description
HAL_RCC_SetSYSCLKSource(hal_rcc_sysclk_src_t source); Set the system clock source
hal_rcc_sysclk_src_t HAL_RCC_GetSYSCLKSource(void); Get the system clock source
uint32_t HAL_RCC_GetSYSCLKFreq(void); Get the system clock frequency
• Unitary Configuration APIs: HAL_RCC_SetHCLKPrescaler,
HAL_RCC_GetHCLKPrescaler, HAL_RCC_SetPCLK1Prescaler,
HAL_RCC_GetPCLK1Prescaler, etc., are used to configure and retrieve the prescaler
settings for individual buses. These functions allow for more granular control,
configuring one bus at a time. Example for the HCLK1 and PCLK1 relative to the
AHB and APB1 busses:
HAL_RCC_SetHCLKPrescaler(HAL_RCC_HCLK_DIV1);
HAL_RCC_SetPCLK1Prescaler(HAL_RCC_PCLK_DIV1);
141

11.7.5. Peripheral Clock management APIs
The HAL RCC driver must provide a set of services to manage the peripheral clocks on
various buses (AHB1, AHB2, AHB3, APB1, APB2, or APB3). These services enable the user
to:
• Enable or disable the peripheral clocks.
• Reset the peripheral clocks.
• Enable or disable the peripheral clocks in low power mode.
• Enable or disable the peripheral clocks in autonomous mode.
•
11.7.5.1. Peripherals Clock Enable/Disable
The HAL RCC driver must provide functions to enable or disable the AHB1 peripheral clock.
After a reset, the peripheral clock is disabled, and the application software must enable this
clock before using it. These services must be provided as static inline functions with a
redirection to the corresponding LL services
Examples:
__STATIC_INLINE void HAL_RCC_CRC_EnableClock(void)
{
LL_AHB1_GRP1_EnableClock(LL_AHB1_GRP1_PERIPH_CRC);
}
__STATIC_INLINE void HAL_RCC_CRC_DisableClock(void)
{
LL_AHB1_GRP1_DisableClock(LL_AHB1_GRP1_PERIPH_CRC);
}
__STATIC_INLINE hal_rcc_clk_status_t HAL_RCC_CRC_IsEnabledClock(void)
{
return (hal_rcc_clk_status_t)LL_AHB1_GRP1_IsEnabledClock(LL_AHB1_GRP1_PERIPH_CRC);
}
11.7.5.1. Peripherals Reset
The HAL RCC driver must provide functions to reset each peripheral. These services must be
provided as static inline functions with a redirection to the corresponding LL services.
Example
__STATIC_INLINE void HAL_RCC_CRC_Reset(void)
{
LL_AHB1_GRP1_ForceReset(LL_AHB1_GRP1_PERIPH_CRC);
LL_AHB1_GRP1_ReleaseReset(LL_AHB1_GRP1_PERIPH_CRC);
}
11.7.5.1. Peripherals Enable/Disable clock in sleep and stop mode
The HAL RCC driver must provide functions to enable or disable the peripheral clock during
Low Power (Sleep and Stop) mode. Peripheral clock gating in SLEEP and STOP modes can
be used to further reduce power consumption.
After wakeup from SLEEP or STOP modes, the peripheral clock is enabled again. By default,
all peripheral clocks are enabled during SLEEP mode; in STOP mode, the peripheral clock is
enabled only when a peripheral requests the AHB clock. These services must be provided as
static inline functions with a redirection to the corresponding LL services.
__STATIC_INLINE void HAL_RCC_LP_CORDIC_EnableClockInSleepMode(void)
{
LL_AHB1_GRP1_EnableClockStopSleep(LL_AHB1_GRP1_PERIPH_CORDIC);
}
142

__STATIC_INLINE void HAL_RCC_LP_CORDIC_DisableClockInSleepMode(void)
{
LL_AHB1_GRP1_DisableClockStopSleep(LL_AHB1_GRP1_PERIPH_CORDIC);
}
__STATIC_INLINE void HAL_RCC_LP_GPDMA1_EnableClockInStopMode(void)
{
LL_AHB1_GRP1_EnableClockStopSleep(LL_AHB1_GRP1_PERIPH_GPDMA1);
}
__STATIC_INLINE void HAL_RCC_LP_GPDMA1_DisableClockInStopMode(void)
{
LL_AHB1_GRP1_DisableClockStopSleep(LL_AHB1_GRP1_PERIPH_GPDMA1);
}
11.7.6. Peripheral Clock source management APIs
The HAL RCC driver must provide a set of services to control the kernel clock source
configuration for peripherals. These functions allow users to select and retrieve the kernel
clock source for peripherals that have a dedicated kernel clock.
Only functions handling peripherals with a kernel clock are included in this subsection. The
peripheral clock can be selected through the independent
API HAL_RCC_{PERIPHx}_SetKernelClkSource(hal_rcc_{periphx}_clk_src_t
clk_src).
The following table lists the APIs provided to configure and retrieve the kernel clock source
for specific peripherals here in this example the I2C1:
API Description
HAL_RCC_I2C1_SetKernelClkSource(hal_rcc_i2c1_clk_src_t clk_src); Set the kernel clock source for I2C1
hal_rcc_i2c1_clk_src_t HAL_RCC_I2C1_GetKernelClkSource(void); Get the kernel clock source for I2C1
uint32_t HAL_RCC_I2C1_GetKernelClkFreq(void); Get the kernel clock frequency for I2C1
Peripheral Clock Retrieval Services:
The HAL RCC driver must provide simple APIs to retrieve the kernel clock of each type of
peripheral with the peripheral instance as an argument. This is essential for various
applications, including:
• Analog Peripherals: Applications may need to get the analog peripheral clock for
frequency calculations (e.g., TIM Input Compare applications require knowing the
timer frequency).
• COM and Audio Peripherals: The peripheral frequency can be useful for speed
calculations.
• GFX Display: The display peripheral frequency is needed to perform display rate
calculations or tuning.
Notes:
• Special Case for TIM Peripherals: The TIM peripheral has no kernel clock mux
but needs to provide a service that retrieves the clock of these peripherals as the
several applications may need this information.
143

• The LPUART is handled by HAL UART.
Examples:
uint32_t HAL_RCC_UART_GetKernelClkFreq(const USART_TypeDef *uartx)
{
uint32_t frequency;
if (uartx == USART1)
{
frequency = HAL_RCC_USART1_GetKernelClkFreq();
}
...
else if (uartx == UART5)
{
frequency = HAL_RCC_UART5_GetKernelClkFreq();
}
#if defined (USART6)
else if (uartx == USART6)
{
frequency = HAL_RCC_USART6_GetKernelClkFreq();
}
#endif /* USART6 */
else if (uartx == LPUART1)
{
frequency = HAL_RCC_LPUART1_GetKernelClkFreq();
}
else
{
frequency = 0U;
}
return frequency;
}
uint32_t HAL_RCC_TIM_GetKernelClkFreq(const TIM_TypeDef *timx)
{
uint32_t frequency;
if (IS_TIM_APB1_INSTANCE(timx) != 0U)
{
frequency = HAL_RCC_GetPCLK1Freq();
if (LL_RCC_GetAPB1Prescaler() != LL_RCC_APB1_DIV_1)
{
frequency *= 2U;
}
}
else if (IS_TIM_APB2_INSTANCE(timx) != 0U)
{
frequency = HAL_RCC_GetPCLK2Freq();
if (LL_RCC_GetAPB2Prescaler() != LL_RCC_APB2_DIV_1)
{
frequency *= 2U;
}
}
else
{
frequency = 0U;
}
return frequency;
}
Usage within the HAL PPP drivers:
144

In the HAL PPP driver side, an API must be provided to return the frequency in Hz of the
PPPi used in the given handle. This API must take the handle as an imput and must be based
on the dedicated RCC APIs HAL_RCC_PPP_GetKernelClkFreq.
This API allows to provide the user with an agnostic service (versus the physical instance that is
linked to the handle)
Examples:
uint32_t HAL_UART_GetClockFreq(const hal_uart_handle_t *huart)
{
USART_TypeDef *p_uartx;
ASSERT_DBG_PARAM((huart != NULL));
ASSERT_DBG_STATE(huart->global_state, HAL_UART_STATE_CONFIGURED);
p_uartx = (USART_TypeDef *)((uint32_t)huart->instance);
return HAL_RCC_UART_GetKernelClkFreq(p_uartx);
}
uint32_t HAL_TIM_GetClockFreq(const hal_tim_handle_t *htim)
{
ASSERT_DBG_PARAM((htim != NULL));
ASSERT_DBG_STATE(htim->global_state, HAL_TIM_STATE_IDLE | HAL_TIM_STATE_ACTIVE));
return HAL_RCC_TIM_GetKernelClkFreq(TIM_INSTANCE(htim));
}
11.7.7. Reset System Clock Configuration
The HAL RCC must provide a function to reset the RCC (Reset and Clock Control) clock
configuration to the default system clock.
Example:
/**
* @brief Reset the RCC clock configuration to the default system clock (MSIS at 4 MHz)
* @note SystemCoreClock and Systick are updated in this function.
* @retval HAL_OK System clock switched to MSIS (4MHz)
* @retval HAL_ERROR Timeout issue to enable the MSIS oscillator\n
* Switch to MSIS as source clock failed\n
* Issue to reconfigure the System tick
*/
hal_status_t HAL_RCC_ResetSystemClock(void);
11.7.8. RCC reset
The HAL RCC must provide a function to reset the RCC (Reset and Clock Control) clock
configuration and perform various reset actions. Example:
/**
* @brief Reset the RCC clock configuration and perform various reset actions.
* @note The following actions are performed:
* 1. Disable RCC interrupts (under the compilation flag
USE_HAL_RCC_RESET_PERIPH_CLOCK_MANAGEMENT)
* 2. Reset all peripherals clock enable
* 3. Reset all peripherals clock source selection
* 4. Reset System clock
* 5. Reset all bus dividers
* 6. Reset all oscillators except those used for the System clock
* 7. Reset all PLLs
* 8. Turn off CSS and MCO
145

* 9. Clear all RCC flags
* @note The Systick frequency and the global variable SystemCoreClock are also updated in this
function.
* @note The implementation is optimized to minimize instructions.
* @retval None
*/
void HAL_RCC_Reset(void);
11.7.9. Additional HAL RCC Services
The HAL RCC driver must provide a set of additional services, depending on the availability
of the feature in the given series. These services include configuring the MCO, managing reset
flags, enabling the Clock Security System, and more.
Examples:
void HAL_RCC_SetConfigMCO(hal_rcc_mco_src_t mco_src, hal_rcc_mco_div_t
mco_div);
uint32_t HAL_RCC_GetResetSource(void);
void HAL_RCC_EnableCSS(void);
void HAL_RCC_NMI_IRQHandler(void);
void HAL_RCC_CSSCallback(void);
11.8. HAL Time base management
The HAL drivers are based on internal time base that must provide the following services:
• HAL Delay: Blocking delay service in milliseconds unit.
• HAL Timeout: The HAL blocking model is based on internal state machine that handle
a complete hardware operation. To avoid blocking the HAL processes, these later are
built around a timeout management model that guarantee to unblock the blocking HAL
services, if the internal hardware behavior has not been correctly done.
• HAL time measures: basic get time operation that can be used by the application to
measure the duration of an event.
The HAL time base is initialized in the first called HAL function HAL_Init () by calling the
function “HAL_UpdateCoreClock” that update the variable “SystemCoreClock” and calls
HAL_InitTick().
hal_status_t HAL_Init(void)
{
...
return HAL_UpdateCoreClock();
}
hal_status_t HAL_UpdateCoreClock(void)
{
SystemCoreClock = ... /* calculate the CPU clock using the HAL RCC services */
/* Configure the source of time base considering new system clocks settings */
return HAL_InitTick(uwTickFreq, uwTickPrio);
}
146

• Within the HAL RCC module, the HAL time base must be re-configured (re-
initialized) by calling the “HAL_UpdateCoreClock” function within tow functions
only that are “HAL_RCC_ResetSystemClock” and “HAL_RCC_Reset”. It must not
be done for other HAL RCC APIs, instead, when the user has end configure the system
clock using the various oscillators, PLL clock source and prescaller APIs he must call
explicitly the function “HAL_UpdateCoreClock” to update the the variable
“SystemCoreClock” and initalizae the HAL time base.
The different time base variables are defined in the common HAL file (stm32tnxx_hal.c/h) as
exportable global variables as follows:
• stm32tnxx_hal.c
volatile uint32_t uwTick;
uint32_t uwTickPrio = ((1UL << __NVIC_PRIO_BITS) - 1UL); /* Initial value: low priority */
hal_tick_freq_t uwTickFreq = HAL_TICK_FREQ_DEFAULT; /* 1KHz */
• stm32tnxx_hal.h
extern volatile uint32_t uwTick; /*!< HAL tick counter current value (unit: ms) */
extern uint32_t uwTickPrio; /*!< HAL tick interrupt priority */
extern hal_tick_freq_t uwTickFreq; /*!< HAL tick frequency */
The default HAL time base configuration is based on the CPU systick.
__WEAK hal_status_t HAL_InitTick(hal_tick_freq_t tick_freq, uint32_t tick_priority)
{
hal_status_t status = HAL_ERROR;
ASSERT_DBG_PARAM(IS_TICK_FREQ(tick_freq));
ASSERT_DBG_PARAM(IS_TICK_PRIO(tick_priority));
/* Check uwTickFreq for MisraC 2012 (despite variable of enum type that does not take value zero) */
if ((uint32_t)uwTickFreq != 0U)
{
/* Note: Value "1000" to convert SysTick frequency value to Hz */
if (HAL_CORTEX_SYSTICK_SetFreq(1000UL / (uint32_t)tick_freq) == HAL_OK)
{
uwTickFreq = tick_freq;
HAL_CORTEX_NVIC_SetPriority(SysTick_IRQn, (hal_cortex_nvic_preemp_priority_t)tick_priority,
(hal_cortex_nvic_sub_priority_t)0U);
uwTickPrio = tick_priority;
status = HAL_OK;
}
}
return status;
}
11.8.1. Changing the time base tick period and priority
The HAL time base management is built by default on a 1ms tick period (i.e., 1 KHz).
However, this default configuration may lead to functional issues when the core operates at
low system frequencies. To address this, additional time base services must be defined in the
common HAL file (stm32tnxx_hal.c/.h), allowing the selection of one of the following tick
frequencies:
typedef enum
{
HAL_TICK_FREQ_10HZ = 100U, /*!< HAL tick frequency 10Hz, , 100ms tick period */
HAL_TICK_FREQ_100HZ = 10U, /*!< HAL tick frequency 100Hz, 10ms tick period */
HAL_TICK_FREQ_1KHZ = 1U, /*!< HAL tick frequency 1kHz, 1ms tick period */
147

HAL_TICK_FREQ_DEFAULT = HAL_TICK_FREQ_1KHZ /*!< HAL tick default frequency: 1kHz */
} hal_tick_freq_t;
Additionally, the user might need to change the tick priority to accommodate the overall
application interrupt requirements. By default, the tick priority is set to the lowest possible
value. Adjusting the tick priority allows for balancing regular tick handling with the need to
ensure that critical interrupts are processed promptly. This adjustment helps achieve as regular
tick handling as possible while ensuring that critical interrupts are not delayed by the tick
interrupt.
uint32_t uwTickPrio = ((1UL << __NVIC_PRIO_BITS) - 1UL); /* Initial value: lowest priority */
These options provide flexibility to accommodate different system frequency requirements
and ensure reliable time base management across various operating conditions.
11.8.2. HAL tick increment
The HAL_IncTick function must be designed to increment the global variable uwTick, which
serves as the application's time base. Typically, this function must be invoked within the
SysTick interrupt service routine (ISR) in the default implementation. The function is marked
with the __WEAK attribute, allowing it to be overridden by other implementations in user-
defined files if necessary. The core operation of the function involves adding the value of the
global variable uwTickFreq (representing the tick frequency and effectively holding the tick
period) to uwTick, effectively updating the application's time base.
/**
* @brief This function is called to increment a global variable @ref uwTick
* used as application time base.
* @note In the default implementation, this function is called within Systick ISR.
* @note This function is declared as __WEAK to be overridden in case of other
* implementations in user file.
*/
__WEAK void HAL_IncTick(void)
{
uwTick += (uint32_t)uwTickFreq;
}
11.8.3. HAL delays
The HAL_Delay function is a blocking delay service in milliseconds unit. The HAL delay is
an exported service that can be used by the application. It must be implemented as a weak
function as following:
__WEAK void HAL_Delay(uint32_t delay_ms)
{
uint32_t tickstart = HAL_GetTick();
uint32_t wait = delay_ms;
/* check wait value before increment to avoid integer wraparound */
if (wait < (HAL_MAX_DELAY - (uint32_t)uwTickFreq))
{
/* Add a delay to guarantee a minimum wait of one period of "tick Frequency" */
wait += (uint32_t)(uwTickFreq);
}
while ((HAL_GetTick() - tickstart) < wait)
{
}
}
Note:
148

The HAL delay period could be lightly increased if several IRQ handler are asserted during a
delay. If the delay must be used accurately and taking into account the IRQ handling timing
The time base could be customized to use interrupt model with higher priority. Using the time
base in interrupt model will require taking into account the several IRQ priorities level to
prevent dead lock condition.
11.8.4. HAL get tick
The HAL_GetTick function is intended to return the current tick value in milliseconds. This
function is declared with the __WEAK attribute, which allows it to be overridden by other
implementations in user-defined files if needed. When called, the function simply returns the
value of the global variable uwTick, providing the current tick count in milliseconds.
/**
* @brief Provides a tick value in milliseconds.
* @note This function is declared as __WEAK to be overridden in case of other
* implementations in user file.
* @retval uint32_t HAL tick current value (unit: milliseconds)
*/
__WEAK uint32_t HAL_GetTick(void)
{
return uwTick;
}
11.8.5. HAL get tick priority and frequency
he HAL_GetTickPrio function is designed to return the current tick priority. When invoked, it
retrieves and returns the value of the global variable uwTickPrio, which represents the priority
level of the tick.
The HAL_GetTickFreq function is intended to return the current tick frequency setting. When
called, it retrieves and returns the value of the global variable uwTickFreq, which indicates the
frequency at which the tick is set.
/**
* @brief This function returns a tick priority.
* @retval uint32_t HAL tick priority
*/
uint32_t HAL_GetTickPrio(void)
{
return uwTickPrio;
}
/**
* @brief Return tick frequency.
* @retval hal_tick_freq_t HAL tick frequency setting
*/
hal_tick_freq_t HAL_GetTickFreq(void)
{
return uwTickFreq;
}
11.8.6. HAL tick suspends and resume
The HAL_SuspendTick function is used to suspend the tick increment. In the default
implementation, the SysTick timer serves as the time base, generating interrupts at regular
intervals. When HAL_SuspendTick is called, it disables the SysTick interrupt, effectively
149

suspending the tick increment. This function is marked with the __WEAK attribute, allowing
it to be overridden by other implementations in user-defined files if necessary.
The HAL_ResumeTick function is used to resume the tick increment. In the default
implementation, the SysTick timer is the source of the time base, generating interrupts at
regular intervals. When HAL_ResumeTick is called, it enables the SysTick interrupt, allowing
the tick increment to resume. This function is also declared with the __WEAK attribute, which
permits it to be overridden by other implementations in user-defined files if needed.
/**
* @brief Suspend Tick increment.
* @note In the default implementation , SysTick timer is the source of time base. It is
* used to generate interrupts at regular time intervals. Once HAL_SuspendTick()
* is called, the SysTick interrupt will be disabled and so Tick increment
* is suspended.
* @note This function is declared as __WEAK to be overridden in case of other
* implementations in user file.
*/
__WEAK void HAL_SuspendTick(void)
{
HAL_CORTEX_SYSTICK_Suspend();
}
/**
* @brief Resume Tick increment.
* @note In the default implementation , SysTick timer is the source of time base. It is
* used to generate interrupts at regular time intervals. Once HAL_ResumeTick()
* is called, the SysTick interrupt will be enabled and so Tick increment
* is resumed.
* @note This function is declared as __WEAK to be overridden in case of other
* implementations in user file.
*/
__WEAK void HAL_ResumeTick(void)
{
HAL_CORTEX_SYSTICK_Resume();
}
11.8.7. HAL timeout
Timeouts are often used for HAL services operating in the polling model. They define the
maximum time within which a blocking process must complete or the minimum time it must
wait for an event to occur. For example:
hal_status_t HAL_UART_Transmit(hal_uart_handle_t *huart, const void *p_data, uint32_t size_byte,
uint32_t timeout_ms);
hal_status_t HAL_DMA_PollForXfer(hal_dma_handle_t *hdma, hal_dma_xfer_level_t xfer_level, uint32_t
timeout_ms);
The timeout has the following ranges:
Timeout value Description
0 No poll: Immediate process check and exit
1 ... (HAL_MAX_DELAY(1)- 1) Timeout in millisecond
HAL_MAX_DELAY(1) Infinite poll till process condition is checked true.
(1)HAL_MAX_DELAY is defined in the stm32tnxx_hal_def.h as 0xFFFFFFFF
The HAL timeouts should be implemented and used inside the polling functions as follows:
150

• Initial Tick Capture: Use HAL_GetTick() to capture the current tick count at the start
of the function.
• Polling Loop: Continuously check the condition (e.g., peripheral readiness) within a
loop.
• Timeout Check:
o Compare the elapsed time (HAL_GetTick() - tickstart) with the
specified timeout_ms value.
o If the timeout is reached, perform additional checks and actions before
returning the status.
• Return Status:
o Before returning HAL_TIMEOUT, recheck the condition to handle
multithreading cases where the timeout might have been reached due to the
function being pre-empted by another process.
o If the timeout is reached and the condition is still not met, take appropriate
actions to end the current polling process, such as disabling the peripheral if
needed, clearing flags, and setting the appropriate state back to IDLE (global
state or process state).
o Return the appropriate status based on whether the timeout has occurred, or the
condition has been met.
hal_status_t HAL_PPP_PollProcess (hal_ppp_handle_t *hppp, uint32_t timeout_ms)
{
uint32_t tickstart = HAL_GetTick(); // Capture the initial tick count
(…)
while (CONDITION)
{
(…)
if((timeout_ms != HAL_MAX_DELAY) && ((timeout_ms == 0)|| \
((HAL_GetTick() - tickstart ) > timeout_ms)))
{
if(!CONDITION)
{
/* Disable the peripheral */
...
/* Clear all the flags */
...
/* Set State to IDLE */
hppp->global_state = HAL_PPP_STATE_IDLE;
return HAL_TIMEOUT;
}
}
}
(…)
}
In some cases, a fixed timeout can be used for system peripherals or internal HAL driver
processes. In these scenarios, the timeout has the same meaning and is used in the same way
as a user-defined timeout, except for two key differences:
• The timeout is defined locally within the driver and cannot be modified or introduced
as an argument by the user.
• The process returns HAL_ERROR instead of HAL_TIMEOUT, as this represents an
internal timeout issue not due to exceeding a user-defined timeout.
151

#define LOCAL_PROCESS_TIMEOUT 100
hal_status_t HAL_PPP_Function (hal_ppp_handle_t *hppp, ...)
{
uint32_t tickstart = HAL_GetTick(); // Capture the initial tick count
(…)
while (CONDITION)
{
(…)
if((HAL_GetTick() - tickstart ) > LOCAL_PROCESS_TIMEOUT)
{
if(CONDITION)
{
/* Disable the peripheral */
...
/* Clear all the flags */
...
/* Set State to IDLE */
hppp->global_state = HAL_PPP_STATE_IDLE;
return HAL_ERROR;
}
}
}
(…)
}
11.8.8. Tick-less timeout
The HAL high-level processes are based on polling, interrupt, and DMA models and utilize the
HAL time-base for internal delays and timeouts. The HAL services in the polling model contain
blocking statements based on the time base, thus, it is forbidden to call them within the ISR
context.
If the above rule is followed, there will be no interrupt priority deadlock condition between the
HAL tick priority and the peripheral HAL drivers. If ISR contexts need to call HAL services
with blocking statements, the HAL tick priority must be the highest one. However, this can lead
to priority conflicts for different HAL processes.
Blocking statements are allowed in the start process functions in DMA and IT models in specific
cases (e.g., filling/dumping FIFO). However, these blocking statements must not rely on the
HAL time base (IT dependency); they should be managed in a tickless mode, i.e., by counting
CPU cycles. This is mandatory to allow calling IT and DMA start processes within the IT and
DMA process callbacks.
The use of CPU cycle counting involves converting a timeout or delay period into a number of
CPU instructions and decrementing it until it reaches zero.
The count variable is then calculated using the timeout or delay in milliseconds and divided by
the number of CPU cycles per second.
The delay and the timeout can be then implemented as follows:
• Timeout:
volatile uint32_t count = SystemCoreClock * TIMEOUT / 1000/ CYCLES_NBR ;
do
{
count--;
if (count == 0)
{
152

break;
}
}
while (Condition on Reg or field);
This applies also for the HAL_PPP_IRQHandler when there is a need to check a flag (the wait
loop must be deterministic, finite and as short as possible (typically using the above pseudo-
code).
• Delay:
void MyDelay(uint32_t mdelay)
{
volatile uint32_t Delay = mdelay * (SystemCoreClock / 1000/ CYCLES_NBR );
do
{
__NOP();
}
while (Delay --);
}
11.9. HAL OS Abstraction Layer
The HAL OS Abstraction Layer is designed to provide a unified interface for operating system
services, ensuring that the HAL can implement Acquire and Release services, such
as HAL_PPP_AcquireBus and HAL_PPP_ReleaseBus, allowing to take and release a HAL
PPP handle for bus-like peripherals (I2C, SPI, UART, etc.).
HAL OSAL must be implemented through the stm32_hal_os.c/h files, which should include
services for semaphores and mutexes, such as creation, taking, releasing, and deletion. These
services are crucial for managing access to shared resources in a multitasking environment.
The stm32_hal_os.c/h files should provide:
• Semaphore Services: Create, take, release, and delete semaphores. These services are
to be used in the HAL_PPP_AcquireBus and HAL_PPP_ReleaseBus APIs when
the USE_HAL_MUTEX define is set to 1.
• Mutex Services: Create, take, release, and delete mutexes.
The HAL OSAL can also be utilized by part drivers' IO interfaces or any other applicative
layer as a simple OSAL wrapper to create, take, release, and delete semaphores and mutexes.
Implementations
The stm32_hal_os.c/h files are provided with two implementations:
• FreeRTOS
For systems utilizing an operating system, the HAL OS Abstraction Layer must include a
FreeRTOS implementation. This version leverages FreeRTOS APIs to manage semaphores
and mutexes, ensuring efficient and reliable synchronization between tasks. The FreeRTOS
implementation supports dynamic allocation, enabling flexible resource management.
stm32_hal_os.h header file
/**
******************************************************************************
* @file stm32_hal_os.h
* @author MCD Application Team
* @brief Header file of STM32 HAL OS: implementation for FreeRTOS.
******************************************************************************
*/
153

#ifndef STM32_HAL_OS
#define STM32_HAL_OS
#ifdef __cplusplus
extern "C" {
#endif
#include "freertos.h"
#include "semphr.h"
#define HAL_OS_TIMEOUT_FOREVER portMAX_DELAY
typedef enum
{
HAL_OS_OK = 0x00,
HAL_OS_ERROR = 0x01
} hal_os_status_t;
typedef SemaphoreHandle_t hal_os_semaphore_t;
typedef SemaphoreHandle_t hal_os_mutex_t;
hal_os_status_t HAL_OS_SemaphoreCreate (hal_os_semaphore_t *p_sem);
hal_os_status_t HAL_OS_SemaphoreTake(hal_os_semaphore_t *p_sem, uint32_t timeout);
hal_os_status_t HAL_OS_SemaphoreRelease(hal_os_semaphore_t *p_sem);
hal_os_status_t HAL_OS_SemaphoreDelete(hal_os_semaphore_t *p_sem);
hal_os_status_t HAL_OS_MutexCreate (hal_os_mutex_t *p_mutex);
hal_os_status_t HAL_OS_MutexTake(hal_os_mutex_t *p_mutex, uint32_t timeout);
hal_os_status_t HAL_OS_MutexRelease(hal_os_mutex_t *p_mutex);
hal_os_status_t HAL_OS_MutexDelete(hal_os_mutex_t *p_mutex);
#ifdef __cplusplus
}
#endif
#endif /* STM32_HAL_OS */
Example of implementation
/**
* @brief Take a semaphore that was created previously.
* @param p_sem Pointer to a hal_os_semaphore_t structure.
* @param timeout_ms The time to wait for the semaphore to become available in ms.
* @retval HAL_OS_OK Semaphore taken successfully.
* @retval HAL_OS_ERROR The timeout_ms expired without the semaphore becoming available.
*/
hal_os_status_t HAL_OS_SemaphoreTake(hal_os_semaphore_t *p_sem, uint32_t timeout_ms)
{
SemaphoreHandle_t hsemaphore = (SemaphoreHandle_t) * p_sem;
hal_os_status_t status = HAL_OS_ERROR;
BaseType_t yield;
if (hsemaphore != NULL)
{
if ((__get_IPSR() != 0U))
{
if (timeout_ms == 0U)
{
yield = pdFALSE;
if (xSemaphoreTakeFromISR(hsemaphore, &yield) == pdPASS)
{
status = HAL_OS_OK;
portYIELD_FROM_ISR(yield);
}
}
}
else
{
if (xSemaphoreTake(hsemaphore, (TickType_t)timeout_ms) == pdPASS)
{
154

status = HAL_OS_OK;
}
}
}
return status;
}
• NO_OS
In addition to the FreeRTOS version, the HAL OS Abstraction Layer must provide a NO_OS
implementation for systems that do not use an operating system. This version is tailored for
ARM architectures, with specific implementations for ARM V7/V8 and ARM V6. The
NO_OS version uses atomic operations and critical sections to manage semaphores and
mutexes, ensuring safe and efficient operation in a bare-metal environment. The ARM V7/V8
implementation utilizes exclusive load and store instructions (__LDREXW and __STREXW)
for atomic operations, while the ARM V6 implementation relies on critical sections to achieve
atomicity.
stm32_hal_os.h header file
/**
******************************************************************************
* @file stm32_hal_os.h
* @author MCD Application Team
* @brief Header file of STM32 HAL OS: implementation for NO OS.
******************************************************************************
*/
#ifndef STM32_HAL_OS
#define STM32_HAL_OS
#ifdef __cplusplus
extern "C" {
#endif
#include "stdint.h"
#define HAL_OS_TIMEOUT_FOREVER 0xFFFFFFFF
typedef enum
{
HAL_OS_OK = 0x00,
HAL_OS_ERROR = 0x01
} hal_os_status_t;
typedef uint32_t hal_os_semaphore_t;
typedef uint32_t hal_os_mutex_t;
hal_os_status_t HAL_OS_SemaphoreCreate (hal_os_semaphore_t *p_sem);
hal_os_status_t HAL_OS_SemaphoreTake(hal_os_semaphore_t *p_sem, uint32_t timeout);
hal_os_status_t HAL_OS_SemaphoreRelease(hal_os_semaphore_t *p_sem);
hal_os_status_t HAL_OS_SemaphoreDelete(hal_os_semaphore_t *p_sem);
hal_os_status_t HAL_OS_MutexCreate (hal_os_mutex_t *p_mutex);
hal_os_status_t HAL_OS_MutexTake(hal_os_mutex_t *p_mutex, uint32_t timeout);
hal_os_status_t HAL_OS_MutexRelease(hal_os_mutex_t *p_mutex);
hal_os_status_t HAL_OS_MutexDelete(hal_os_mutex_t *p_mutex);
#ifdef __cplusplus
}
#endif
#endif /* STM32_HAL_OS */
155

Example of implementation for ARM V7/V8
/**
* @brief Take a semaphore that was created previously.
* @param p_sem Pointer to a hal_os_semaphore_t structure.
* @param timeout_ms The time to wait for the semaphore to become available in ms.
* @retval HAL_OS_OK Semaphore taken successfully.
* @retval HAL_OS_ERROR The timeout_ms expired without the semaphore becoming available.
*/
hal_os_status_t HAL_OS_SemaphoreTake(hal_os_semaphore_t *p_sem, uint32_t timeout_ms)
{
hal_os_status_t status = HAL_OS_ERROR;
uint32_t tickstart = HAL_GetTick();
uint32_t time_over = 0;
if ((__get_IPSR() != 0U) && (timeout_ms != 0U))
{
return status;
}
else
{
do
{
if (__LDREXW(p_sem) == 0U)
{
if (__STREXW(1, p_sem) == 0U)
{
status = HAL_OS_OK;
}
}
if (timeout_ms != HAL_OS_TIMEOUT_FOREVER)
{
if (((HAL_GetTick() - tickstart) > timeout_ms) || (timeout_ms == 0U))
{
time_over = 1;
}
}
} while ((time_over == 0U) && (status != HAL_OS_OK));
}
/* Do not start any other memory access until memory barrier is complete */
__DMB();
return status;
}
Example of implementation for ARM V6
/**
* @brief Take a semaphore that was created previously.
* @param p_sem Pointer to a hal_os_semaphore_t structure.
* @param timeout_ms The time to wait for the semaphore to become available in ms.
* @retval HAL_OS_OK Semaphore taken successfully.
* @retval HAL_OS_ERROR The timeout_ms expired without the semaphore becoming available.
*/
hal_os_status_t HAL_OS_SemaphoreTake(hal_os_semaphore_t *p_sem, uint32_t timeout_ms)
{
hal_os_status_t status = HAL_OS_ERROR;
uint32_t tickstart = HAL_GetTick();
uint32_t time_over = 0;
if ((__get_IPSR() != 0U) && (timeout_ms != 0U))
{
return status;
}
156

else
{
do
{
HAL_ENTER_CRITICAL_SECTION();
/* Check if the lock is taken by a different thread */
if ((*p_sem) == 0U)
{
*p_sem = 1U;
status = HAL_OS_OK;
}
HAL_EXIT_CRITICAL_SECTION();
if (timeout_ms != HAL_OS_TIMEOUT_FOREVER)
{
if (((HAL_GetTick() - tickstart) > timeout_ms) || (timeout_ms == 0U))
{
time_over = 1;
}
}
} while ((time_over == 0U) && (status != HAL_OS_OK));
}
/* Do not start any other memory access until memory barrier is complete */
__DMB();
return status;
}
Customization
The HAL OSAL must provide template of stm32_hal_os.c/h files with an empty
implementation of the various services. These files serve as a skeleton of the required HAL
OS APIs that can be implemented by users who need to customize the HAL OSAL
implementation. This customization is necessary for users who are implementing a custom OS
or require a custom implementation of the HAL OSAL. By providing this skeleton, users have
a structured starting point to develop their own OS abstraction, ensuring compatibility and
integration with the HAL.
By providing these implementations, the HAL OS Abstraction Layer can be used in a wide
range of applications, from complex systems with an RTOS to simple bare-metal systems.
This flexibility allows developers to choose the appropriate level of abstraction and
synchronization mechanism based on their specific application requirements.
stm32_hal_os.h template header file
/**
******************************************************************************
* @file stm32_hal_os.h
* @author GPM Application Team
* @brief Header file of STM32 HAL OS: implementation for MY OS.
******************************************************************************
*/
#ifndef STM32_HAL_OS
#define STM32_HAL_OS
#ifdef __cplusplus
extern "C" {
#endif
#include "my_os.h"
#define HAL_OS_TIMEOUT_FOREVER MY_OS_MAX_DELAY
157

typedef enum
{
HAL_OS_OK = 0x00,
HAL_OS_ERROR = 0x01
} hal_os_status_t;
typedef My_OS_Semaphore_t hal_os_semaphore_t;
typedef My_OS_Mutex_t hal_os_mutex_t;
hal_os_status_t HAL_OS_SemaphoreCreate(hal_os_semaphore_t *p_sem);
hal_os_status_t HAL_OS_SemaphoreTake(hal_os_semaphore_t *p_sem, uint32_t timeout_ms);
hal_os_status_t HAL_OS_SemaphoreRelease(hal_os_semaphore_t *p_sem);
hal_os_status_t HAL_OS_SemaphoreDelete(hal_os_semaphore_t *p_sem);
hal_os_status_t HAL_OS_MutexCreate(hal_os_mutex_t *p_mutex);
hal_os_status_t HAL_OS_MutexTake(hal_os_mutex_t *p_mutex, uint32_t timeout_ms);
hal_os_status_t HAL_OS_MutexRelease(hal_os_mutex_t *p_mutex);
hal_os_status_t HAL_OS_MutexDelete(hal_os_mutex_t *p_mutex);
#ifdef __cplusplus
}
#endif
#endif /* STM32_HAL_OS */
Example of empty implementation in the stm32_hal_os.c template
/**
* @brief Take a semaphore that was created previously.
* @param p_sem Pointer to a hal_os_semaphore_t structure.
* @param timeout_ms The time to wait for the semaphore to become available in ms.
* @retval HAL_OS_OK Semaphore taken successfully.
* @retval HAL_OS_ERROR The timeout_ms expired without the semaphore becoming available.
*/
hal_os_status_t HAL_OS_SemaphoreTake(hal_os_semaphore_t *p_sem, uint32_t timeout_ms)
{
return HAL_OS_ERROR;
}
11.10. HAL over LL layering model
The HAL (Hardware Abstraction Layer) must be designed to provide a high-level, user-
friendly interface for interacting with hardware peripherals. It must be built on top of the LL
(Low-Layer) drivers, which offer a more granular and direct control over the hardware
registers. The HAL abstracts the complexity of the LL drivers by encapsulating their
functionalities into higher-level functions and services, making it easier for developers to
configure and control peripherals without needing to manage the intricate details of register-
level programming. This layered approach ensures that while the HAL provides ease of use
and portability across different hardware platforms, it can still leverage the performance and
precision of the LL drivers when needed. This design allows developers to choose the
appropriate level of abstraction based on their application requirements, balancing ease of use
with control and efficiency.
Furthermore, the HAL is structured to rely on the LL drivers for register access operations,
such as reading from or writing to hardware registers. This reliance ensures that all register
manipulations are performed through the LL drivers, which are optimized for direct hardware
interaction. By delegating register access to the LL drivers, the HAL maintains a consistent
and reliable method for interacting with the hardware, while also benefiting from the
robustness and efficiency of the LL layer. This approach not only enhances code
maintainability and readability but also ensures that any updates or optimizations in the LL
158

drivers automatically benefit the HAL, leading to a more cohesive and efficient system
overall.
In addition, the HAL focuses on several key aspects to ensure robust and reliable operation.
These include parameter checking, state transitions, and logical sequences for configuration
and processing as described in the reference manual. The HAL is responsible for validating
input parameters to prevent erroneous configurations, managing state transitions to ensure
peripherals operate correctly, and following logical sequences for initialization, configuration,
and operation. Moreover, the HAL facilitates interaction with the user through various return
values and callbacks, providing feedback and enabling event-driven programming. This
comprehensive approach ensures that the HAL not only simplifies peripheral control but also
enhances the overall reliability and user experience.
In counterpart, the LL focuses on providing highly efficient APIs to read, write, or modify
registers and fields in strict accordance with the STM32 reference manuals. The LL drivers are
designed to offer low-level access to the hardware, remaining faithful to the hardware
description and ensuring optimal performance. While the HAL aims to remain compatible
across different STM32 series for common operations like transmit and receive, the LL drivers
are tailored to the specific hardware, providing direct and efficient control. This distinction
allows the HAL to offer a uniform interface for application development, while the LL ensures
that the underlying hardware is utilized to its full potential.
Notes:
• Some system HALs, such as
the Cortex, are implemented on top
of the CMSIS core services. The principle remains that the HAL does not directly
access the registers when an LL (Low-Layer) driver is provided or when the service is
provided by the CMSIS core.
• When neither an LL driver nor a HAL core driver (e.g., HAL FDCAN) is provided, the
HAL driver is permitted to perform direct register access.
159

12. LL drivers
12.1. Overview
The Low Layer (LL) drivers are part of the STM32Cube firmware HAL, providing a basic set
of optimized, one-shot services. Unlike the HAL drivers, the LL drivers are not fully portable
across all STM32 families; the availability of certain functions depends on the physical
presence of the corresponding features in the specific product.
The Low Layer (LL) drivers are designed to offer the following features:
• A et of inline functions for direct and atomic register access.
• One-shot operations that can be used by the HAL drivers or at the application level.
• Fully independent from HAL, allowing standalone usage without HAL drivers.
• Comprehensive feature coverage for all supported peripherals.
Note: The LL initialization functions (C file) are no longer available on HAL2. If a user needs
to initialize a given peripheral using the LL layer, he must rely on code generation with the LL
layer. This generates the required sequence based on the LL Low, Middle, and High-level
APIs available in the header (.h) files. The given generated sequence provides a better
footprint optimization versus the previous LL Init functions.
From architecture point of view, the low layer drivers are in the same level of core drivers, the
core drivers are called internally by the HAL drivers to provide common intrinsic services for
several HAL drivers which share the same peripheral hardware block while the low layer
drivers provide low level services to both HAL drivers and application.
The LL drivers are designed to provide hardware services based on the available features of
the STM32 peripherals. These services are reflecting exactly the hardware capabilities and
provide One-shot operations that must be called following the programming model of the
reference manual document. The LL services are not based on standalone processes and do not
need any additional memory resources to save their states, counter or data pointers, all the
operations have to be performed by changing the associated peripheral registers content.
All the LL drivers are called through their physical instance (Peripheral registers structures
mapped on the peripherals base registers), only system peripherals do not need to be called
through their instance.
160

The LL drivers are given in one module for each physical peripheral located in a separate
header file. These files are called within the HAL drivers . when using the LL drivers at the
application side, the LL header files must be included through the LL file inclusion model
with no additional project setting.
12.2. Low Layer files
The Low-Layer drivers are built around one single header file per peripheral. The LL drivers
are implemented in header files only (no “c” files) with functions provided as static inline.
Files Description
Common (for all stm32tnxx_ll_utils.h The LL UTILS driver contains a set of generic APIs that can be
series) used for:
• Device electronic signature
• Timing functions
stm32tnxx_ll_system.h The LL SYSTEM driver contains a set of generic APIs that can
be used to:
• Get the device unique ID
• get the package device type
stm32tnxx_ll_bus.h This is the h-source file for core bus control and peripheral
clock activation and deactivation
Example: LL_AHB2_GRP1_EnableClock
Peripheral drivers stm32tnxx_ll_ppp.h This is the h-source file of the PPP low layer driver. The low
layer PPP driver is a standalone module. To be used,
application must include the stm32tnxx_ll_ppp.h
Note: When the low layer is used with the HAL drivers, there is
no need to include the given LL header files in the application.
Contrary to the HAL drivers, the low-layer ones are not built on process model but rather in
simple access operations on registers. Thus, the low-layer drivers have no configuration file.
For the common drivers:
LL driver APIs
LL system __STATIC_INLINE uint32_t LL_GetPackageType(void)
__STATIC_INLINE uint32_t LL_GetUID_Word0(void)
__STATIC_INLINE uint32_t LL_GetUID_Word1(void)
__STATIC_INLINE uint32_t LL_GetUID_Word2(void)
LL util /* Initialize SysTick for 1ms based on SysTick overflow flag */
__STATIC_INLINE void LL_InitTick(uint32_t cpuclk_frequency, uint32_t ticks)
/* Delay in ms based on SysTick overflow flag */
__STATIC_INLINE void LL_Delay_NoISR(uint32_t delay_ms)
The low layer files are in the “ll” folder.
161

Notes:
▪ All the low layer files must be delimited by the peripheral availability
#if defined (PPP)
(…)
#endif /* PPP */
Or in case of multi-instances:
#if defined (PPP1) || (…) || defined (PPPN)
(…)
#endif /* PPP1 || PPPn */
12.3. APIs definition levels
The LL drivers’ scope is to provide an abstraction APIs level that covers the snippets
functions and some of the standard peripheral library functionalities. The low layer drivers
provide a complementary set of basic functions for the HAL drivers to allow the customization
or the replacement of some high-level processes. The following figure summarizes the
functions coverage level for all the ST firmware offers:
Each LL peripheral driver must provide the following three APIs levels:
162

12.3.1. low level
This level includes the LL_PPP_WRITE_REG () / LL_PPP_READ_REG (redirection of
CMSIS registers operations) and the LL_PPP_DMA_GET_REG_ADDR:
Multi instances peripherals:
/**
* @brief Write a value in PPP register.
* @param instance PPP Instance.
* @param reg Register to be written.
* @param value Value to be written in the register.
* @retval None.
*/
#define LL_PPP_WRITE_REG(instance, reg, value) WRITE_REG(((instance)->reg), (value))
/**
* @brief Read a value in PPP register.
* @param instance PPP Instance.
* @param reg Register to be read.
* @retval Register value.
*/
#define LL_PPP_READ_REG(instance, reg) READ_REG(instance->reg)
Single instance peripherals (system peripheral):
/**
* @brief Write a value in PPP register
* @param reg Register to be written
* @param value Value to be written in the register
*/
#define LL_PPP_WRITE_REG(reg, value) WRITE_REG(PPP->reg, (value))
/**
* @brief Read a value in PPP register
* @param reg Register to be read
* @retval Register value
*/
#define LL_PPP_READ_REG(reg) READ_REG(PPP>reg)
Note: The LL_PPP_DMA_GET_REG_ADDR () API is a common interface for DMA relative
registers for all peripherals to prevent using direct register access in DMA config API. This
API provides only the address of the register used for DMA transfer. It is used only for
configuration, thus, conditional check is allowed. For optimal use, we can always use direct
register access. The LL_PPP_DMA_GetRegAddr() prototype is defined as follows :
__STATIC_INLINE uint32_t LL_PPP_DMA_GET_REG_ADDR (PPP_TypeDef *p_ppp {Sub Instance if any ex: channel},
{uint32_t property }) (1)
(1)
Parameters inside braces are to be omitted when not used.
12.3.2. Middle level
This level includes one shot operations APIs (atomic) and the elementary LL_PPP_SetItem()
and LL_PPP_Action() functions:
LL_ADC_Enable ();
LL_LPTIM_SetCounterMode()
LL_LPTIM_StartCounter()
12.3.3. High level
This level includes global configuration and initialization functions that cover full standalone
operations on relative peripheral registers:
LL_RCC_PLL_ConfigDomain_SAI(uint32_t source, uint32_t pll_m, uint32_t pll_n, uint32_t pll_p)
LL_RTC_TIME_Config(uint32_t hour, uint32_t minute, uint32_t second)
163

12.4. APIs Categories
For Low Layer drivers APIs visibility and in order to explicitly differentiate common actions
associated with different modes and feature, some APIs are categorized, the category notion
could refer to the hardware mode, feature and physical subblock, depending on the peripheral.
The following table shows categories associated with some supported peripherals:
Peripheral Associated categories
ALL DMA: DMA Get Data address APIs
ADC INJ: injected mode
REG: Regular mode
RTC TIME
DATE
ALARMA
ALARMB
TIMESTAMP
TAMPER
WAKEUP
BAK: backup
CAL: calibration
TIM CC: capture compare
OC: output compare
IC: Input capture
RCC HSE
HSI
HSI48
LSI
LSCO
MSI
PLLx (with x depending from the given STM32 series)
12.5. Functions coding rules
Low layer functions must be defined to have direct or indirect access (register basis + offset
from LL function parameter) and unconditional register access,
__STATIC_INLINE void LL_PPP_SetConfigItem (PPPx_TypeDef *p_ppp, uint32_t value)
{
WRITE_REG (p_ppp->REG, ADJUST (value));
}
Thus, if else statements are not allowed. However, exception is made when registers naming,
or bits definition or sequence might differ across instances1.
__STATIC_INLINE void LL_PPP_SetConfigItem (PPPx_TypeDef *p_ppp, uint32_t value)
{
if(p_ppp == PPPA)
{
WRITE_REG (p_ppp->REGISTERA, ADJUST(2) (value));
}
else
{
WRITE_REG (p_ppp->REGISTERB, ADJUST (value));
}
}
1 this exception does not include Specific Interrupt and status flags management rule.
2 ADJUST macro refers to the mathematical processing (shift, masking…etc) made on the value.
The compile time conditional checks are allowed to limit functions scope according to
physical availability of the peripheral or specific features:
164

#if defined (PPP)
(specific feature)
#endif
Example:
#if defined(QUADSPI)
__STATIC_INLINE void LL_RCC_SetQSPIClockSource(uint32_t clk_source) { }
#endif /* QUADSPI */
#if defined (FEATURE_BIT_DEFINITION)
(specific feature)
#endif
Example:
#if defined(PWR_CR1_SRAM3PD)
__STATIC_INLINE void LL_PWR_SetSRAM3RunRetention(uint32_t sram3_retention)
{
MODIFY_REG(PWR->CR1, LL_PWR_SRAM3_RUN_FULL_RETENTION, ((~sram3_retention) &
LL_PWR_SRAM3_RUN_FULL_RETENTION));
}
__STATIC_INLINE uint32_t LL_PWR_GetSRAM3RunRetention(void)
{
return ((~(READ_BIT(PWR->CR1, LL_PWR_SRAM3_RUN_FULL_RETENTION))) & LL_PWR_SRAM3_RUN_FULL_RETENTION);
}
#endif /* defined(PWR_CR1_SRAM3PD) */
The compile time conditional checks are also allowed to customize a functions
implementation according to physical availability of the peripheral or specific features:
Example:
__STATIC_INLINE void LL_COMP_ConfigInputs(COMP_TypeDef *p_comp, uint32_t input_minus, uint32_t
input_plus)
{
#if defined (COMP_CFGRX_INP2SEL)
MODIFY_REG(p_comp->CFGR,
COMP_CFGRx_INMSEL | COMP_CFGRx_INPSEL |
COMP_CFGRx_INP2SEL |
COMP_CFGRx_SCALEN | COMP_CFGRx_BRGEN,
input_minus | input_plus);
#else
MODIFY_REG(COMPx->CFGR,
COMP_CFGRx_INMSEL | COMP_CFGRx_INPSEL |
COMP_CFGRx_SCALEN | COMP_CFGRx_BRGEN,
Input_minus | input_plus);
#endif
}
Important Note:
For both HAL and LL drivers, it is prohibited to use the device RPN define as compile-time
conditional checks (e.g., #if defined(STM32U535xx)). Instead, the implementation must rely
on dedicated defines for peripherals, features, or feature bits, as described above.
This approach simplifies the maintenance of HAL and LL drivers when new derivatives of the
same series are introduced. In such cases, the Device Family Pack (DFP) should be updated
with the new device header file, which must include the necessary defines for peripherals and
features.
165

As a result, HAL and LL drivers will automatically support the new device derivatives without
requiring modifications, provided the peripherals and features remain consistent. Updates to
HAL and LL drivers are only necessary if the new derivative introduces new use cases or
features.
Indirect access is preconized, when a status flag or Interrupt or an activation field could be
located in different registers following the sub-instance (channel, stream…etc), it is
recommended to calculate the addressed register offset through the sub-instance index.
Example:
__STATIC_INLINE void LL_PPP_ClearIT_XXX (PPP_TypeDef *p_ppp, uint32_t sub_index)
{
STM32_WRITE_REG (p_ppp->REG + CALC_OFFSET (sub_index), PPP_REG_XXXX)
}
12.6. Functions prototypes
All the low layer APIs for a PPP peripheral must be defined in the stm32yxxx_ll_ppp.h with
the following rule:
__STATIC_INLINE return_type LL_PPP_Function (PPPx_TypeDef *p_ppp, args)
{
(Function body)
}
Some form of extra effort to call the function faster than it would otherwise, generally by
substituting the code of the function into its caller. As well as eliminating the need for a call
and return sequence, it might allow the compiler to perform certain optimizations between the
bodies of both functions.
Sometimes it is necessary for the compiler to emit a stand-alone copy of the object code for a
function even though it is an inline function - for instance if it is necessary to take the address
of the function, or if it can't be inlined in some particular context, or if optimization has been
turned off.
Note: There are various ways to define inline functions; any given kind of definition might
definitely emit stand-alone object code, definitely not emit stand-alone object code, or only
emit stand-alone object code if it is known to be needed. Sometimes this can lead to
duplication of object code. Low layer functions are defined in static inline. Thus, local
definition may be emitted if required. Multiple definitions are possible in the application, in
different translation units, and it will still work. Just dropping the inline reduces the program
to a portable one (again, all other things being equal).
12.7. Functions arguments
The low layer APIs are defined as static inline, except the helper services, which are to be
defined as macros. These functions might have no argument or multi arguments. The
maximum number of arguments is fixed to 4 to allow high code optimization and full usage of
core register without using the stack, exception is made when the arguments are to be loaded
in the same register, in this case, more than 4 arguments could be used.
__STATIC_INLINE return_type LL_PPP_Function (PPPx_TypeDef *p_ppp, args)
{
166

(Function body)
}
Item Description Possible Values
return_type return value type ▪ void
▪ {u}intx_t where x could be 8/16/32
p_ppp peripheral instance (not required for system ▪ Depend on product Part number (ex: ADC1)
peripherals)
args functions’ arguments (can be omitted or with more ▪ void
arguments)
▪ {u}intx_t where x could be 8/16/32
Data pointers are not allowed, the low layer handle only single data transfer and it is up to the
application to manage multiple data transfer. Memory addresses are to be defined uintx_t
(where x could be 8/16/32) following the transfer mode and it is up to the application to use
the right transfer API or make the cast of a different user pointer type.
LL_PPP_TransmitData8 (PPPx, data8);
LL_PPP_TransmitData16 (PPPx, data16);
Example: USART
LL_USART_TransmitData8 (PPPx, data8);
LL_USART_TransmitData9 (PPPx, data16);
Notes:
1- In the LL layer, enumerated types are not allowed to minimize ORed definition conflict.
2- Defines must be aligned to the HAL literals and enumerated types to ease redefinition.
Examples:
a. in the HAL, HAL_GPIO_PIN_0 is a define redirected to the equivalent define in
the low layer GPIO driver.
b. In the HAL, the GPIO mode is an enumeration, the possible values are redirected
to their equivalent in the low layer GPIO driver.
3- Defines must be inherited from bit definition in CMSIS files. Example:
Examples
#define LL_GPIO_PIN_0 GPIO_BSRR_BS0 /*!< Select pin 0 */
#define LL_GPIO_PIN_1 GPIO_BSRR_BS1 /*!< Select pin 1 */
#define HAL_GPIO_PIN_0 LL_GPIO_PIN_0 /*!< GPIO pin 0 */
#define HAL_GPIO_PIN_1 LL_GPIO_PIN_1 /*!< GPIO pin 1 */
#define LL_GPIO_MODE_INPUT 0x00000000U /*!< Select input mode */
#define LL_GPIO_MODE_OUTPUT GPIO_MODER_MODE0_0 /*!< Select output mode */
#define LL_GPIO_MODE_ALTERNATE GPIO_MODER_MODE0_1 /*!< Select alternate function mode */
#define LL_GPIO_MODE_ANALOG GPIO_MODER_MODE0 /*!< Select analog mode */
typedef enum
{
HAL_GPIO_MODE_INPUT = LL_GPIO_MODE_INPUT, /*!< Input Floating mode */
HAL_GPIO_MODE_OUTPUT = LL_GPIO_MODE_OUTPUT, /*!< Output mode */
HAL_GPIO_MODE_ALTERNATE = LL_GPIO_MODE_ALTERNATE, /*!< Alternate mode */
HAL_GPIO_MODE_ANALOG = LL_GPIO_MODE_ANALOG /*!< Analog mode */
} hal_gpio_mode_t;
4- The following peripherals do not require to be instantiated:
167

Peripherals (IPs)
System FLASH/NVM
DBGMCU, SYSCFG, SBS (LL functions handled in the stm32tnxx_ll_system.h file)
EXTI
PWR
RCC
SYSCFG/SBS
RTC
TAMP
5- By default, the returned value is uint32_t, even for Boolean value, however for data read
and reception, depending on the data width the returned value can be {u}intx_t where x
could be 8/16/32. Examples:
__STATIC_INLINE uint32_t void LL_PPP_IsEnabledIT_XX (PPP_TypeDef *p_ppp);
__STATIC_INLINE uint8_t LL_PPP_ReceiveData8 (PPPx);
__STATIC_INLINE uint16_t LL_PPP_ReceiveData9 (PPPx);
12.8. Functions implementation
12.8.1. Local variables
The Low layer functions must not use additional resources than core and peripheral registers.
Both global variables and objects (structure) are not allowed. The low layer drivers can use
only local variables. Local variables used to make logical operations before loading them into
register, must be always in 32bits variable. Typically, local variables are placed in registers by
the compiler, instead of on the (stack) frame of the function. Using the core registers is very
efficient because they do not require memory accesses, so the compiler can use shorter/faster
instructions when working with them.
__STATIC_INLINE void LL_PPP_SetConfigItem (PPPx_TypeDef *p_ppp, uint32_t value)
{
uint32_t tmp = 0;
tmp = (value)) << 4;
tmp |= CONVERT (value) ;
WRITE_REG (p_ppp->REG, tmp);
}
Local variables usage must be limited and if possible, use internal core registers for register
bits handling. Therefore, the function above can be defined as follows:
__STATIC_INLINE void LL_PPP_SetConfigItem (PPPx_TypeDef *p_ppp, uint32_t Value)
{
WRITE_REG (p_ppp->REG, ADJUST (value));
}
12.8.2. Operations on registers
It is recommended to handle the register operation using the following exported macros from
the cmsis files, Ex:
STM32_SET_BIT(REG, BIT)
STM32_CLEAR_BIT(REG, BIT)
STM32_READ_BIT(REG, BIT)
168

STM32_CLEAR_REG(REG)
STM32_WRITE_REG(REG, VAL)
STM32_READ_REG(REG)
STM32_MODIFY_REG(REG, CLEARMASK, SETMASK)
12.8.3. Boolean operations
The returned Boolean value is always uint32_t, Example:
__STATIC_INLINE uint32_t LL_PPP_IsEnabledIT_XX (PPP_TypeDef *p_ppp);
Internal implementation must as follows:
__STATIC_INLINE uint32_t LL_PPP_IsItem_XXX (PPP_TypeDef *PPPx)
{
  return ((READ_BIT(PPPx->REG, BIT_DEFINITION) == (BIT_DEFINITION)) ? 1UL : 0UL);
}

12.9. Naming rules
12.9.1. Naming convention
The following tables summarize the common words and phrases to be used for some standard
operations:
| Class  | Category  | Operation  | Word / Phrase  |
| ------ | --------- | ---------- | -------------- |

|     |     | Send data     | TransmitDataFormat  |
| --- | --- | ------------- | ------------------- |
|     |     | Receive data  | ReceiveDataFormat   |

|     |     | Fix data alignment  | SetDataWidth  |
| --- | --- | ------------------- | ------------- |
Communication
|     |     | Set Transfer length       | SetDataLength    |
| --- | --- | ------------------------- | ---------------- |
|     |     | Abandon current transfer  | Abort            |
|     |     | Write Data                | WriteDataFormat  |
Storage
|     |                 | Read Data                       | ReadDataFormat  |
| --- | --------------- | ------------------------------- | --------------- |
|     |                 | Activate a feature or a mode    | EnableItem      |
|     |                 |                                 |                 |
|     |                 | Deactivate a feature or a mode  | DisableItem     |
|     | Activation and  |                                 |                 |
|     | deactivation    |                                 |                 |
|     |                 | Return activation state         | IsEnabled       |

|          |     | Clear a bit  | ClearItem  |
| -------- | --- | ------------ | ---------- |
| Generic  |     |              |            |
|          |     | Set a bit    | SetItem    |
Bit handling
|     |     | Read a bit (Boolean)  | IsEnabledItem  |
| --- | --- | --------------------- | -------------- |
IsActiveItem
|     |     | Set a single configuration value  | SetItem  |
| --- | --- | --------------------------------- | -------- |

|     |     | Set multiple configuration values  | ConfigItem  |
| --- | --- | ---------------------------------- | ----------- |
Configuration

|     |     | Get a configuration value             | GetItem       |
| --- | --- | ------------------------------------- | ------------- |
|     |     | Perform a Specific action on an item  | Action{Item}  |
Specific action
|     |     | Check whether an operation is done  | IsOperation(verb in past tense)  |
| --- | --- | ----------------------------------- | -------------------------------- |

Notes:
1-  Enable/Disable actions have no extra parameters beyond the instance ex:
LL_ADC_Enable(ADCx);
169

2- Set action keyword is used to handle only one item at once ex:
LL_SPI_SetMemDataWidth (SPIx, 32);
3- For SetAction, additional indirect arguments could be used, but they are not
configuration item ex: LL_USART_SetBaudRate (USART2, HCLK,
LL_USART_BAUDRATE_9600) ; HCLK is used to calculate BRR value but the
configuration item is only LL_USART_BAUDRATE_9600
4- Config keyword is used when several items are needed to make a full configuration ex:
LL_RCC_PLL_Config (SRC,M, N, R)
Definitions:
Description Example
Item Refer to the action relative to the LL_USART_SetBaudRate
configuration item to be updated.
Action/Operation Refer to a specific operation to handle a LL_ADC_StartConversion
specific feature:
• Force
• Release
• Start
• Stop
• Reload
• Request
• Acknowledge
• Generate
• Update
• Insert
• Select
• Ongoing
Format Refer to the data width, it must be an LL_USART_TransmitData8
integer value depending on the physical
data width to be handled
Operation Refer to a specific operation state for a LL_ADC_IsCalibrated
specific feature
Names/identifiers must not have more than 31 non-unique significant characters (MISRA C:
2012 Rule-5.1). This does not mean that names cannot be longer than 31 characters, just that
any two or more identifiers must NOT be identical in the first 31 characters. Any
names/identifiers that exceed 31 significant characters must be abbreviated.
When appropriate, all name/identifier words and tokens must be abbreviated using the
STM32Cube firmware abbreviation table (See STM32Cube Firmware Specification). Note
that this rule covers only the second phrase part and not the action word i.e. for “EnableItem”
only the “Item” part must follow the abbreviation rule.
12.9.1. General naming rules
Item Name Example
170

File name stm32tnxx_ll_ppp (h) stm32tnxx_ll_adc.h
Function name LL_PPP{_CATEGORY}_Function (PPPx, ARGS) LL_USART_SetBaudRate (USART2, HCLK,
format LL_USART_BAUDRATE_9600) ;
LL_RCC_HSI_Enable ()
MACRO __LL_PPP{_CATEGORY}_ITEM (ARG1, __LL_RTC_YEAR (RTC)
ARG2….ARGN)
Define Format LL_PPP{_CATEGORY}_ITEM{_VALUE} LL_USART_BAUDRATE_9600
▪ The PPP prefix refers to the peripheral name as defined in Stm32tnxx reference
manuals ex: ADC
▪ Registers are considered as constants. In most cases, their name is in uppercase and
uses the same acronyms as in the Stm32tnxx reference manuals.
▪ Peripheral registers are declared in the PPP_TypeDef structure (e.g. ADC_TypeDef)
in stm32tnxxx.h header file. stm32tnxxx.h corresponds to stm32f401xc.h,
stm32f401xe.h, stm32f405xx.h, stm32f415xx.h, stm32f407xx.h, stm32f417xx.h,
stm32f427xx.h, stm32f437xx.h, stm32f429xx.h or stm32f439xx.h
12.9.2. Functions naming rules
The format of the low layer functions is defined according to the following format:
__STATIC_INLINE return_type LL_PPP_Function (PPPx_TypeDef *PPPx, args)
The “Function” naming part must be one of the following according to the action category:
▪ Specific Interrupt, DMA request and status flags management:
Set/Get/Clear/Enable/Disable flags on interrupt and status registers
Name Examples
LL_PPP_{_CATEGORY}_ActionItem_BITNAME ▪ LL_RCC_ClearFlag_FWRST()
LL_PPP{_CATEGORY}_IsItem_BITNAME_Action ▪ LL_RCC_IsActiveFlag_FWRST()
▪ LL_ADC_ClearFlag_EOC(ADC1)
▪ LL_DMA_ClearFlag_TC(DMAx,
channel)
The possible functions format is list in the following table:
171

Item Action Format
Get LL_PPP_IsActiveFlag_BITNAME
Flag Clear LL_PPP_ClearFlag_BITNAME
Enable LL_PPP_EnableIT_BITNAME
Disable LL_PPP_DisableIT_BITNAME
Interrupt
Get LL_PPP_IsEnabledIT_BITNAME
Enable LL_PPP_EnableDMAReq_BITNAME
Disable LL_PPP_DisableDMAReq_BITNAME
DMA
Get LL_PPP_IsEnabledDMAReq_BITNAME
Notes:
▪ The BITNAME must be the same as defined in the STM32 product
documentation.
▪ The letter relative to Interrupt, Flag bit handling action as defined in the
STM32 product documentations must be removed example: LSIRDYF must be
renamed LSIRDY
▪ If removing the letter relative to Interrupt, Flag bit handling action, create a
non-significant short name, the flag BITNAME could be changed with an
explicit abbreviated name, example: UIE must be used as follows UPDATE
▪ When handling multiple interrupt and status flags, it is recommended to use the
exported macros from the CMSIS files, Ex:
- STM32_SET_BIT(REG, BIT)
- STM32_CLEAR_BIT(REG, BIT)
- STM32_READ_BIT(REG, BIT)
- STM32_CLEAR_REG(REG)
- STM32_WRITE_REG(REG, VAL)
- STM32_READ_REG(REG)
- STM32_MODIFY_REG(REG, CLEARMASK, SETMASK)
- STM32_POSITION_VAL(VAL)
▪ Peripherals clock activation/deactivation management: Enable/Disable/Reset a
peripheral clock
Name Example
LL_BUS_GRPx_ActionClock{Mode} ▪ LL_AHB2_EnableClock (LL_AHB2_GPIOA|
LL_AHB2_GPIOB)
▪ LL_APB1_EnableClockSleep (LL_APB1_DAC1)
x: corresponding to group index, it refers to the index of modified register on a bus.
▪ Peripherals activation/deactivation management: Enable/Disable a peripheral or
activate/Deactivate specific peripheral features
Name Example
172

LL_PPP{_CATEGORY}_Action{Item} ▪ LL_ADC_Enable ()
LL_PPP{_CATEGORY}_IsItemAction ▪ LL_ADC_EnableCalibration();
▪ LL_ADC_IsCalibrated();
▪ LL_RCC_HSI_Enable ()
▪ LL_RCC_HSI_IsReady()
▪ Peripheral configuration management: Set/Get a peripheral configuration value
Name Example
LL_PPP{_CATEGORY}_Set{ or Get}ConfigItem ▪ LL_USART_SetBaudRate (USART2, Clock,
LL_USART_BAUDRATE_9600)
▪ Peripheral register’s management: Write/Read a register or return DMA relative
register address
Name
LL_PPP_WRITE_REG (instance, reg , value)
LL_PPP_READ_REG (instance, reg)
LL_PPP_DMA_GET_REG_ADDR (PPP_TypeDef *p_ppp,{Sub Instance if any ex: Channel} , {uint32_t
Propriety})
Propriety: variable used to identify a register, it can be direction, data register type etc…
12.9.3. Macros naming rules
▪ Helper operations: formatting of an argument to fit register bitfields values
Name Example
LL_PPP{_CATEGORY}_ITEM (ARG1, ARG2….ARGN) ▪ LL_RTC_YEAR (RTC)
NOTE: Helper macros are only used for values computation or conversion or register offset
calculation for internal driver use (for more information refer to the “Functions definition
rules” section.
12.9.4. Literal’s naming rules
Name Example
LL_PPP{_CATEGORY}_ITEM_VALUE ▪ LL_RCC_HSE_ADCCLKSOURCE _DIVx
▪ LL_USART_BAUDRATE_9600
LL_PPP{_CATEGORY}_ITEM ▪ LL_I2C_OVRF
173

12.9.5. Functions definition rules
The Low Layer drivers are designed to provide basic set of optimized and one shot services.
In the application, these services must be called following the programming model of the
reference manual document. The functions scope is in contrary of the HAL is not based on
high level process but rather in basic operations on core and peripherals registers. The
definition of the low layer APIs must target both friendly user API concept and optimized
registers access.

The following rules provide the necessary recommendations to define the APIs for a specific
peripheral:

1-  Interrupts, DMA requests and status flags must be always coded with only one (or two, in
case of modify operation) register operation and defined according to the following
format:

| Item  | Action  |                              | Format  |     |
| ----- | ------- | ---------------------------- | ------- | --- |
|       |         | LL_PPP_IsActiveFlag_BITNAME  |         |     |
|       | Get     |                              |         |     |
| Flag  |         |                              |         |     |
|       |         | LL_PPP_ClearFlag_BITNAME     |         |     |
Clear
|     |     |     |     |     |
| --- | --- | --- | --- | --- |

|     | Enable  | LL_PPP_EnableIT_BITNAME  |     |     |
| --- | ------- | ------------------------ | --- | --- |

|     | Disable  | LL_PPP_DisableIT_BITNAME  |     |     |
| --- | -------- | ------------------------- | --- | --- |
Interrupt
|     | Get     | LL_PPP_IsEnabledIT_BITNAME   |     |     |
| --- | ------- | ---------------------------- | --- | --- |
|     | Enable  | LL_PPP_EnableDMAReq_BITNAME  |     |     |

LL_PPP_DisableDMAReq_BITNAME
| DMA  | Disable  |     |     |     |
| ---- | -------- | --- | --- | --- |
LL_PPP_IsEnabledDMAReq_BITNAME
Get
Examples:
__STATIC_INLINE void LL_USART_ClearFlag_PE(USART_TypeDef *p_usart)
{
  WRITE_REG(p_usart->ICR, USART_ICR_PECF);
}

__STATIC_INLINE uint32_t LL_USART_IsEnabledIT_PE(USART_TypeDef *p_usart)
{
  return ((READ_BIT(p_usart->CR1, USART_CR1_PEIE) == (USART_CR1_PEIE)) ? 1UL : 0UL);
}

2-  Identify peripheral functional blocks and related services and features. A service must
provide a standalone action on a feature even if it can be used or modified by another
block. The service must then be associated with unitary “Get” operations to be able to
restore already set items when only configuration has to be updated or changed.

174

Example: for the PLLs in the RCC peripherals, Typical related APIs could be defined
as follows:
Standalone services :
LL_RCC_PLL_ConfigDomain_SYS(uint32_t source, uint32_t pll_m, uint32_t pll_n, uint32_t pll_r)
LL_RCC_PLL_ConfigDomain_SAI(uint32_t source, uint32_t pll_m, uint32_t pll_n, uint32_t pll_p)
LL_RCC_PLL_ConfigDomain_48M(uint32_t source, uint32_t pll_m, uint32_t pll_n, uint32_t pll_q)
Unitary services:
LL_RCC_PLL_GetDivider(void)
LL_RCC_PLL_GetMainSource(void)
LL_RCC_PLL_GetN(void)
LL_RCC_PLL_GetQ(void)…etc
In user code, when an item must be updated, for instance SRC field in the example below, the
unitary “Get” operations could be used to restore already set values:
LL_RCC_PLL_ConfigDomain_SYS (src, LL_RCC_PLL_GetDivider (), pll_n, LL_RCC_PLL_GetPLLR ())
3- Same scope low layer APIs must be defined in a homogeneous way and have the same
action/item naming, even the two peripherals are not belonging to the same peripheral
class (for instance, Communication peripheral). Example: In the DMA LL driver, the
LL_DMA_SetMemDataWidth () function is used to set the DMA data width, and the same
feature is present in the SPI peripheral, so it is recommended to use the same naming as
follows: LL_SPI_SetMemDataWidth ().
4- When a status flag or Interrupt or an activation field could be located in different registers
following the sub-instance (channel, stream…etc), it is recommended to calculate the
addressed register offset through the sub-instance index. Example:
__STATIC_INLINE void LL_PPP_ClearIT_XXX (PPP_TypeDef *p_ppp, uint32_t sub_index)
{
WRITE_REG (p_ppp->REG + CALC_OFFSET (sub_index), PPP_REG_XXXX)
}
175

5- When there is no direct mathematic formula to calculate the offset, or no additional timing
due to the offset computations, it is recommended to define a static constant table (LUT) to
minimize the processing time in the LL functions. Note that MISRA C rules must be
applied to prevent cast issues.
__STATIC_INLINE void LL_PPP_Action (PPP_TypeDef *p_ppp, uint32_t sub_index)
{
WRITE_REG (p_ppp->REG + OFFSET_TAB [sub_index], PPP_REG_XXXX)
}
Example:
__STATIC_INLINE void LL_DMA_DisableStream(DMA_TypeDef *p_dma, uint32_t Stream)
{
uint32_t dma_base_addr = (uint32_t)p_dma;
CLEAR_BIT(((DMA_Stream_TypeDef *)(dma_base_addr + LL_DMA_STR_OFFSET_TAB[Stream]))->CR, DMA_SxCR_EN);
}
6- Rule 5 could be applied as well on the status flag or Interrupt or an activation field bit
definition:
__STATIC_INLINE void LL_PPP_ClearIT_XXX (PPP_TypeDef *p_ppp, uint32_t sub_index)
{
WRITE_REG (p_ppp->REG, LL_PPP_OFFSET_TAB [sub_index])
}
7- A complete register access sequence required to perform a standalone PPP peripheral
functionality by referring to the PPP peripheral associated registers is to be always defined
in a single LL function ex: LL_GPIO_LockPin() .
__STATIC_INLINE void LL_GPIO_LockPin(GPIO_TypeDef* p_gpio, uint32_t pin_msk)
{
WRITE_REG(p_gpio->LCKR, GPIO_LCKR_LCKK | pin_msk);
WRITE_REG(p_gpio->LCKR, pin_msk);
WRITE_REG(p_gpio->LCKR, GPIO_LCKR_LCKK | pin_msk);
READ_REG(p_gpio->LCKR));
}
8- When a complete register access sequence is required to perform a standalone PPP1
peripheral functionality by referring to another PPP2 peripheral associated registers, the
relative PPP1 Low Layer function must only cover the functionality part covered by the
PPP1 registers only. Ex:
LL_PWR_EnableBkUpAccess();
(…)
LL_RTC_EnableInitMode();
9- Timeout, error management and flags querying within loops are always to be implemented
in application level. The Low layer functions must not embed such statements internally.
//Ex: App.c
LL_RCC_HSE_Enable();
LL_RCC_HSE_EnableBypass();
while (true) /* Infinite loop */
176

{
if (LL_RCC_GetSysClockSource() == LL_RCC_SYS_CLKSOURCE_STATUS_HSE)
{
/* Timeout management */
/* Error management */
}
}
10- A Low layer function A must not use statements that might be used by another function B,
when the statement can be used once within a global process example: The low layer
function implementation below is wrong:
__STATIC_INLINE void LL_PPP_ActionA(void)
{
SET_BIT(PPP->REG1, PPP_REG1_BITx);
SET_BIT(PPP->REG2, PPP_REG1_BITy);
}
__STATIC_INLINE void LL_PPP_ActionB(void)
{
SET_BIT(PPP->REG1, PPP_REG1_BITz);
SET_BIT(PPP->REG2, PPP_REG1_BITy);
}
/* complete configuration in application */
LL_PPP_ActionA ();
LL_PPP_ActionB ();
The right implementation is to split LL_PPP_ActionA() and LL_PPP_ActionB() into three
functions as follows:
__STATIC_INLINE void LL_PPP_ActionA(void)
{
SET_BIT(PPP->REG1, PPP_REG1_BITx);
}
__STATIC_INLINE void LL_PPP_ActionB(void)
{
SET_BIT(PPP->REG1, PPP_REG1_BITz);
}
__STATIC_INLINE void LL_PPP_ActionC(void)
{
SET_BIT(PPP->REG2, PPP_REG1_BITy);
}
/* complete configuration in application */
LL_PPP_ActionA ();
LL_PPP_ActionB ();
LL_PPP_ActionC ();
12.10. Usage scenarios
The low layer is designed to be used in standalone mode or combined with HAL. It cannot be
automatically used with the HAL for the same peripheral instance. When using the LL APIs
for a specific instance, User can still use the HAL APIs for other instances. The main
constraint is when the LL overwrite some registers that the content might NOT be mirrored in
the HAL handles.
177

12.10.1. User application based on LL only
The low layer can be used without the call of the HAL drivers’ services by simply including
stm32tnxx_ll_ppp.h in the application files.
The LL APIs for a peripheral are called with the same sequence recommended by the
programming model in the reference manual of the used product. For this case the HAL
drivers associated with the peripheral in use can be removed from the workspace, however the
STM32Cube framework must be used in the same way as for the HAL drivers case i.e. System
file, startup file, CMSIS must be always used.
Notes:
• The stm32_ll.h is provided as a template and includes all the LL driver header files of
the given series. In the case of code generation, this file will contain only the selected
LL driver components. Users can utilize the copied file as is, where all LL drivers of
the given STM32 family are included, or customize it to keep only the required LL
driver's inclusion. This flexibility allows users to optimize their application by
including only the necessary LL drivers, thereby reducing the code footprint and
improving maintainability.
178

12.10.2. User application with mixed HAL and LL
Mixed use is allowed; however, some considerations must be taken into account:
• Configuration APIs:
o It is not allowed to use the HAL configuration APIs and the combination of
low-layer APIs for the same instance simultaneously. Some configuration
parameters could impact the handle's internal parameters, which are not visible
to the LL APIs.
o It is recommended to ensure the full configuration of the peripheral instance
using the HAL by calling:
▪ The HAL global configuration function.
▪ Additional HAL sub-block configuration functions, if required.
▪ Additional HAL feature configuration functions, if required.
• Process APIs:
o It is not allowed to use the HAL process APIs and the combination of low-layer
APIs for the same instance simultaneously. Some HAL process functions could
impact the handle's internal parameters, which are not visible to the LL APIs.
• Summary:
o The recommendation is to use the HAL to configure the given peripheral
instance without mixing it with the LL functions. If more granularity is needed
in the process starting and control, use the LL functions. However, after
starting to use the LL layer, it is not allowed to revert to using the HAL, as the
LL actions may have an impact that is not represented or synchronized in the
HAL PPP handle.
Notes:
1. When process APIs are not used and the functionality is performed through the low
layer, callbacks are not called. Post-processing or error management must be handled
by the user.
2. When using the LL APIs for process operations, the IRQ handler HAL APIs cannot be
called. The IRQ must be implemented by the user. Each LL driver implements the
required macros to read and clear associated interrupt flags.
12.11. Cohabitation with HAL
The low layer can be used without any constraint with all the HAL drivers that are not based on handle objects
(RCC, Cortex, common HAL, flash and GPIO). However, to cohabitate the HAL with the low layer the user has
to be aware about some HAL concepts.
- The Low layer is intended to be used in expert mode (high knowledge on hardware aspect).
- The HAL drivers are built in a high-level abstraction based on standalone processes that do not need
high knowledge on the hardware PP peripheral.
Several HAL and LL cohabitation schemes listed below have to be considered.
12.11.1. Initializing a peripheral using the Low layer
By default, when the HAL PPP initialization and configuration APIs need to be replaced by
the LL APIs, the application must be written entirely with LL APIs for the addressed instance,
as the HAL processes cannot be used in conjunction with LL APIs.
179

In this scenario, the peripheral handle is no longer used, and therefore, it does not need to be
allocated. Additionally, the HAL PPP IRQ handler should not be called within the PPP
Interrupt Service Routines (PPPi_IRQHandler). It is the responsibility of the user application
to write the required ISR based on the various LL functions that handle the interrupts and
flags. Furthermore, the HAL callbacks are no longer useful, and synchronization with the
application must be ensured by the user's ISR.
12.11.2. Control functions using the Low layer
The control operations generally aim to change, at run-time, the content of some registers that
were initially set using the HAL_PPP_SetConfig or various HAL PPP feature APIs. If the
HAL PPP initialization and configuration APIs are used, and the user only needs to call LL
APIs to update some features, it is recommended to use the HAL_PPP_SetItem,
HAL_PPP_SetFeature, HAL_PPP_EnableFeature, or HAL_PPP_DisableFeature functions
instead. These HAL unitary functions are built using the LL APIs and ensure proper
synchronization with the handles (when needed).
Example:
• To change the counter mode of the TIM, the following unitary function can be
called:
hal_status_t HAL_TIM_SetCounterMode(const hal_tim_handle_t *htim,
hal_tim_counter_mode_t counter_mode);
While the HAL_TIM_SetCounterMode () is defined as follows:
hal_status_t HAL_TIM_SetCounterMode(const hal_tim_handle_t *htim,
hal_tim_counter_mode_t counter_mode)
{
ASSERT_DBG_PARAM((htim != NULL));
ASSERT_DBG_STATE(htim->global_state,
(HAL_TIM_STATE_INIT | HAL_TIM_STATE_IDLE));
tim_t *p_tim = TIM_INSTANCE(htim);
/* Ensure that the instance supports mode selection */
ASSERT_DBG_PARAM(IS_TIM_COUNTER_MODE_SELECT_INSTANCE(p_tim));
/* Check counter mode validity */
ASSERT_DBG_PARAM(IS_TIM_COUNTER_MODE(counter_mode));
LL_TIM_SetCounterMode(p_tim, (uint32_t)counter_mode);
return HAL_OK;
}
And the LL_TIM_SetCounterMode () is defined as follows:
__STATIC_INLINE void LL_TIM_SetCounterMode(TIM_TypeDef *timx, uint32_t mode)
{
MODIFY_REG(timx->CR1, (TIM_CR1_DIR | TIM_CR1_CMS), mode);
}
The HAL_TIM_SetCounterMode function ultimately redirects to
the LL_TIM_SetCounterMode function after performing assertion checks. These assertion
checks are entirely bypassed if the compilation
flags USE_ASSERT_DBG_PARAM or USE_ASSERT_DBG_STATE are not set.
180

• To disable the UART FIFO mode the following function can be called:
hal_status_t HAL_UART_DisableFifoMode(hal_uart_handle_t *huart)
While the HAL_UART_DisableFifoMode () is defined as follows:
hal_status_t HAL_UART_DisableFifoMode(hal_uart_handle_t *huart)
{
USART_TypeDef *p_uartx;
ASSERT_DBG_PARAM(huart != NULL);
p_uartx = (USART_TypeDef *)((uint32_t)huart->instance);
ASSERT_DBG_PARAM(IS_UART_FIFO_INSTANCE((USART_TypeDef *)(uint32_t)huart->instance));
ASSERT_DBG_STATE(huart->global_state, HAL_UART_STATE_CONFIGURED);
ASSERT_DBG_STATE(huart->rx_state, HAL_UART_RX_STATE_IDLE);
ASSERT_DBG_STATE(huart->tx_state, HAL_UART_TX_STATE_IDLE);
UART_ENSURE_INSTANCE_DISABLED(p_uartx);
LL_USART_DisableFIFO(p_uartx);
huart->fifo_mode = HAL_UART_FIFO_MODE_DISABLED;
/* Update Tx and Rx numbers of data to process */
UART_SetNbDataToProcess(huart);
UART_ENSURE_INSTANCE_ENABLED(p_uartx);
return HAL_OK;
}
And the LL_USART_DisableFIFO () is defined as follows:
__STATIC_INLINE void LL_USART_DisableFIFO(USART_TypeDef *p_usart)
{
CLEAR_BIT(p_usart->CR1, USART_CR1_FIFOEN);
}
The HAL_UART_DisableFifoMode function ensures that
the LL_USART_DisableFIFO function is called to effectively disable the FIFO at the register
level. Additionally, it updates the handle's impacted parameters, such as fifo_mode, and
adjusts the number of data items to process through the internal
function UART_SetNbDataToProcess.
12.11.1. Using HAL operation APIs with the Low layer
The HAL I/O operations APIs are generally provided in three models:
• Blocking Model (Polling)
• Interrupt Model
• DMA Model
If one of the above model APIs needs to be replaced by the LL APIs, it is not necessary to
replace the other model APIs. Customized I/O operations APIs do not require the use of LL
APIs for the initialization and configuration provided by HAL.
For DMA and Interrupt model APIs, when customized by the LL, the associated HAL
callbacks cannot be used for the addressed instance.
181

If I/O operations are customized and the user wants to continue using
the HAL_PPP_GetState() and HAL_PPP_GetLastErrorCodes() APIs, the customized
processes must update the state and error fields accordingly.
This approach can be used to customize all or some of the HAL processes, particularly to
improve the performance of time-critical operations. The processes to be customized should
have no dependency on other processes. For example, you can customize the Transmit APIs
with the LL while keeping the Receive APIs with the HAL.
12.12. Internal integration in HAL drivers
In the development of the HAL it is essential to leverage the middle-level LL (Low-Layer)
APIs to replace direct register access. This approach ensures that the HAL functions maintain
efficiency, readability, and alignment with the STM32 reference manuals.
The HAL drivers must:
• Include the low layer required drivers (header file)
• Redirect the HAL defines and enumerations possible values to the equivalent LL
defines
#define HAL_GPIO_PIN_0 LL_GPIO_PIN_0 /*!< GPIO pin 0 */
#define HAL_GPIO_PIN_1 LL_GPIO_PIN_1 /*!< GPIO pin 1 */
#define HAL_GPIO_PIN_2 LL_GPIO_PIN_2 /*!< GPIO pin 2 */
#define HAL_GPIO_PIN_3 LL_GPIO_PIN_3 /*!< GPIO pin 3 */
...
#define HAL_GPIO_PIN_15 LL_GPIO_PIN_15 /*!< GPIO pin 15 */
#define HAL_GPIO_PIN_ALL LL_GPIO_PIN_ALL /*!< GPIO pin all*/
typedef enum
{
182

HAL_GPIO_MODE_INPUT = LL_GPIO_MODE_INPUT, /*!< Input Floating mode */
HAL_GPIO_MODE_OUTPUT = LL_GPIO_MODE_OUTPUT, /*!< Output mode */
HAL_GPIO_MODE_ALTERNATE = LL_GPIO_MODE_ALTERNATE, /*!< Alternate mode */
HAL_GPIO_MODE_ANALOG = LL_GPIO_MODE_ANALOG /*!< Analog mode */
} hal_gpio_mode_t;
• Use Middle level LL APIs when need to set or get a single item:
For instance, when writing a single item, the provided LL functions, such as LL_PPP_SetItem,
should be used. This method not only simplifies the code but also enhances maintainability.
An example is the HAL_DCACHE_Invalidate function, where direct register access is
replaced with LL_DCACHE_SetCommand and LL_DCACHE_Invalidate to set commands
and invalidate the cache, respectively.
Similarly, in the HAL_I2C_GetConfig function, direct register access is substituted with LL
functions like LL_I2C_GetTiming, LL_I2C_GetMasterAddressingMode,
and LL_I2C_GetOwnAddress1. This ensures that the configuration and retrieval processes are
handled efficiently and consistently with the hardware specifications.
Eg:
hal_status_t HAL_SPI_SetBaudRatePrescaler(hal_spi_handle_t *hspi, const hal_spi_baudrate_prescaler_t
baudrate_prescaler)
{
/* Check the SPI handle allocation */
ASSERT_DBG_PARAM(hspi != NULL);
ASSERT_DBG_PARAM(IS_SPI_PRESCALER(baudrate_prescaler));
/* Check the global state */
ASSERT_DBG_STATE(hspi->global_state, HAL_SPI_STATE_IDLE);
/* Set the BaudRate Prescaler */
LL_SPI_SetBaudRatePrescaler((SPI_TypeDef *)((uint32_t)hspi->instance), (uint32_t)baudrate_prescaler);
return HAL_OK;
}
• Use High level LL APIs when need to configure several parameters
When configuring multiple parameters that affect the same register or are within the same
scope, it is essential to use high-level LL APIs within the HAL. These high-level LL APIs are
designed to simplify the process by encapsulating the configuration of several fields into a
single function call. For example, in the case of configuring the RCC (Reset and Clock
Control) MCO (Microcontroller Clock Output) settings, instead of individually setting each
field of the register, the LL_RCC_ConfigMCO API can be used. This API allows setting the
MCO clock source and prescaler in one step, ensuring that the configuration is consistent and
less error-prone. By utilizing these high-level LL APIs, the HAL can efficiently manage
complex configurations, improve code readability, and maintain alignment with the STM32
reference manuals.
183

Considerations:
• Consistency: Using high-level LL APIs ensures that related configurations are applied
consistently, reducing the risk of errors that may arise from manually setting individual
fields.
• Efficiency: High-level LL APIs are optimized for performance, allowing for efficient
configuration of multiple parameters with a single function call.
• Maintainability: Encapsulating multiple configurations within a single API call
improves code maintainability, making it easier to understand and modify.
• Alignment with Reference Manuals: High-level LL APIs are designed in accordance
with the STM32 reference manuals, ensuring that configurations are applied correctly
and as intended by the hardware specifications.
• Error Reduction: By reducing the need for direct register manipulation, high-level LL
APIs minimize the chances of incorrect configurations and potential bugs.
• Simplified Code: High-level LL APIs simplify the code by abstracting complex
configurations into straightforward function calls, enhancing readability and reducing
development time.
o From the HAL side
typedef enum
{
HAL_RCC_MCODIV_1 = LL_RCC_MCO1_DIV_1, /*!< MCO is divided by 1 */
HAL_RCC_MCODIV_2 = LL_RCC_MCO1_DIV_2, /*!< MCO is divided by 2 */
HAL_RCC_MCODIV_4 = LL_RCC_MCO1_DIV_4, /*!< MCO is divided by 4 */
HAL_RCC_MCODIV_8 = LL_RCC_MCO1_DIV_8, /*!< MCO is divided by 8 */
HAL_RCC_MCODIV_16 = LL_RCC_MCO1_DIV_16, /*!< MCO is divided by 16 */
} hal_rcc_mco1_div_t;
typedef enum
{
HAL_RCC_MCO1SOURCE_NOCLOCK = LL_RCC_MCO1SOURCE_NOCLOCK, /*!< MCO1 output disabled, no clock on MCO1
*/
HAL_RCC_MCO1SOURCE_SYSCLK = LL_RCC_MCO1SOURCE_SYSCLK, /*!< SYSCLK selection as MCO1 source */
HAL_RCC_MCO1SOURCE_MSI = LL_RCC_MCO1SOURCE_MSIS, /*!< MSI selection as MCO1 source */
HAL_RCC_MCO1SOURCE_HSI = LL_RCC_MCO1SOURCE_HSI, /*!< HSI selection as MCO1 source */
HAL_RCC_MCO1SOURCE_HSE = LL_RCC_MCO1SOURCE_HSE, /*!< HSE selection as MCO1 source */
HAL_RCC_MCO1SOURCE_PLL1CLK = LL_RCC_MCO1SOURCE_PLLCLK, /*!< PLL1CLK selection as MCO1 source */
HAL_RCC_MCO1SOURCE_LSI = LL_RCC_MCO1SOURCE_LSI, /*!< LSI selection as MCO1 source */
HAL_RCC_MCO1SOURCE_LSE = LL_RCC_MCO1SOURCE_LSE, /*!< LSE selection as MCO1 source */
HAL_RCC_MCO1SOURCE_HSI48 = LL_RCC_MCO1SOURCE_HSI48, /*!< HSI48 selection as MCO1 source */
HAL_RCC_MCO1SOURCE_MSIK = LL_RCC_MCO1SOURCE_MSIK, /*!< MSIK selection as MCO1 source */
} hal_rcc_mco_src_t;
void HAL_RCC_SetConfigMCO(hal_rcc_mco_index_t mcox, hal_rcc_mco_src_t mco_src,
hal_rcc_mco1_div_t mco_div)
{
...
/* Set MCO1 clock source and prescaler */
LL_RCC_ConfigMCO((uint32_t)mco_src, (uint32_t)mco_div);
}
o From the LL side
/**
* @brief Configure MCOx
* @rmtoll CFGR1 MCOSEL LL_RCC_ConfigMCO\n
* CFGR1 MCOPRE LL_RCC_ConfigMCO
* @param mcox_sourc This parameter can be one of the following values:
* @arg @ref LL_RCC_MCO1SOURCE_NOCLOCK
184

* @arg @ref LL_RCC_MCO1SOURCE_SYSCLK
* @arg @ref LL_RCC_MCO1SOURCE_MSIS
* @arg @ref LL_RCC_MCO1SOURCE_HSI
* @arg @ref LL_RCC_MCO1SOURCE_HSE
* @arg @ref LL_RCC_MCO1SOURCE_HSI48
* @arg @ref LL_RCC_MCO1SOURCE_PLLCLK
* @arg @ref LL_RCC_MCO1SOURCE_LSI
* @arg @ref LL_RCC_MCO1SOURCE_LSE
* @param mcox_prescaler This parameter can be one of the following values:
* @arg @ref LL_RCC_MCO1_DIV_1
* @arg @ref LL_RCC_MCO1_DIV_2
* @arg @ref LL_RCC_MCO1_DIV_4
* @arg @ref LL_RCC_MCO1_DIV_8
* @arg @ref LL_RCC_MCO1_DIV_16
* @retval None
*/
__STATIC_INLINE void LL_RCC_ConfigMCO(uint32_t mcox_source, uint32_t mcox_prescaler)
{
MODIFY_REG(RCC->CFGR1, RCC_CFGR1_MCOSEL | RCC_CFGR1_MCOPRE, mcox_sourc | mcox_prescaler);
}
Reducing Register Access: Using high-level LL APIs is essential when needed to minimize
the number of times registers are accessed and modified compared to calling a list of unitary
LL APIs where each modify the same register for a given field.
o Clear Sequencing of HAL APIs Based on LL Services for Simplified Transition
and Maintenance
The implementation of HAL APIs should provide a clear sequence based on LL services for
several reasons. Firstly, it simplifies the reading and maintenance of the HAL driver by clearly
delineating the steps and corresponding LL functions used. This structured approach makes
the code more understandable and easier to debug. Secondly, it allows users to switch from
HAL to LL very easily, as the LL calls are explicitly outlined within the HAL functions. This
facilitates a smoother transition for users who may need more direct control over the
hardware. Additionally, users can start their application development based on the HAL
drivers and later switch to LL drivers for footprint reasons. The transition will be simple
because the LL calls are listed within each HAL API, providing a clear roadmap for migrating
to LL. Lastly, it simplifies the writing of LL Code Generation templates for STM32CubeMX2.
By examining a HAL configuration function, such as HAL_USART_SetConfig, developers
can easily identify the sequence of LL calls required, streamlining the process of generating
LL code.
To enhance efficiency and readability in HAL API implementations, it is essential to use
appropriate high-level LL APIs when multiple fields of the same register need to be set. This
approach prevents multiple writes to the same register, which would occur if using middle-
level LL APIs that set individual fields.
Furthermore, it is important to avoid using LL_PPP_WRITE_REG APIs within HAL
implementations. Instead, equivalent high-level LL APIs should be utilized to maintain clarity
and readability. The use of LL_PPP_WRITE_REG should be limited to situations where
equivalent high-level LL APIs cannot be provided, particularly when the targeted register
fields belong to different scopes.
185

Here is an example of HAL_USART_SetConfig:
hal_status_t HAL_USART_SetConfig(hal_usart_handle_t *husart, const hal_usart_config_t *p_config)
{
USART_TypeDef *p_usartx;
uint32_t instance_clock_freq;
uint32_t cr1_config;
uint32_t cr2_config;
ASSERT_DBG_PARAM(husart != NULL);
ASSERT_DBG_PARAM(p_config != NULL);
#if defined(USE_HAL_CHECK_PARAM) && (USE_HAL_CHECK_PARAM == 1)
if (p_config == NULL)
{
return HAL_INVALID_PARAM;
}
#endif /* USE_HAL_CHECK_PARAM */
ASSERT_DBG_PARAM(IS_USART_PRESCALER(p_config->clock_prescaler));
...
ASSERT_DBG_PARAM(IS_USART_MODE(p_config->mode));
ASSERT_DBG_STATE(husart->global_state, (uint32_t)(HAL_USART_STATE_INIT | HAL_USART_STATE_IDLE));
p_usartx = USART_GET_INSTANCE(husart);
LL_USART_Disable(p_usartx);
if (p_config->mode == HAL_USART_MODE_SLAVE)
{
LL_USART_ConfigSyncSlaveMode(p_usartx);
}
else
{
LL_USART_ConfigSyncMasterMode(p_usartx);
}
husart->usart_mode = p_config->mode;
cr1_config = ((uint32_t)p_config->word_length | (uint32_t)p_config->parity
| (uint32_t)p_config->direction | LL_USART_OVERSAMPLING_8);
cr2_config = ((uint32_t)p_config->stop_bits | (uint32_t)p_config->clock_polarity
| (uint32_t)p_config->clock_phase | (uint32_t)p_config->clock_last_bit);
LL_USART_ConfigXfer(p_usartx, cr1_config, cr2_config);
LL_USART_SetPrescaler(p_usartx, (uint32_t)p_config->clock_prescaler);
instance_clock_freq = HAL_RCC_USART_GetKernelClkFreq(p_usartx);
if (instance_clock_freq == 0U)
{
return HAL_ERROR;
}
LL_USART_SetBaudRate(p_usartx, instance_clock_freq, (uint32_t)p_config->clock_prescaler,
LL_USART_OVERSAMPLING_8, p_config->baud_rate);
/* Enable USART instance */
LL_USART_Enable(p_usartx);
if (USART_CheckEnabledState(husart) != HAL_OK)
{
return HAL_ERROR;
}
186

husart->global_state = HAL_USART_STATE_IDLE;
return HAL_OK;
}
187

13. HAL/LL drivers: security support

The purpose of this chapter is to details the security aspect based at the HAL and LL drivers
based on
-  ARMv8 architecture
-  GTZC and RIF peripherals

13.2. RIF and GTZC HAL and LL drivers

The unification of RIF and Trust Zone APIs is critical due to their similar usage within
application layers, requiring consistent and harmonized interfaces for common features across
both GTZC and RIF drivers. To address this, the architecture enforces attribute management
through dedicated functions designed to ensure code portability across HAL and LL drivers.
These functions must independently manage security, privilege, and lock attributes, as well as
read and write access operations, with clear separation between items and attributes within
function  parameters.  Additionally,  function  implementations  must  support  both  static
configurations—such as establishing security attributes during application initialization by
isolating resources between secure and non-secure, privileged and non-privileged domains—
and dynamic configurations that enable attribute reconfiguration based on evolving application
needs. This approach ensures a flexible, robust, and unified framework for security attribute
management.

The following table lists the HAL and LL RIF and GTZC naming rules:

| Concept  | HAL/LL RIF naming rule  | HAL/LL GTZC naming rule    |
| -------- | ----------------------- | -------------------------- |
wording
Block based  RISAB: Resource isolation slave unit  MPCBB: memory protection controller - Block
| sub-block  | for address space protection (block- | based  |
| ---------- | ------------------------------------ | ------ |
based)
Illegal access  IAC: Illegal access controller  TZIC: Trust Zone illegal access controller
sub-block

Watermark sub- RISAF: Resource isolation slave unit  TZSC_MPCWM: Memory protection controller –
| block  | for address space protection (full  | Watermark  |
| ------ | ----------------------------------- | ---------- |
version)
Periph Attr sub- RIFSC : Resource isolation  TZSC: Trust Zone security controller
| block  | framework security controller   |     |
| ------ | ------------------------------- | --- |
|        | RISC: Resource Isolation Slave  |     |
Controller
RIMC: Resource Isolation Master
Controller
| Illegal access   |         | ilac       |
| ---------------- | ------- | ---------- |
| Region           | region  | N/A        |
| Sub Region       |         | subregion  |
| Security         |         | Sec        |
| Non-Secure       |         | NSec       |
| Privilege        |         | Priv       |
| Read             |         | Rd         |
188

Write Wr
Address Addr
Public Public N/A
Non-Public NPublic N/A
13.2.1. RIF and GTZ HAL driver’s architecture
13.2.1.1.1. Security and privilege attribute APIs for securable peripherals
(RIF_RIFSC/GTZC_TZSC)
The HAL GTZ and RIF driver must follow the following giving the rules for the naming,
enumerations, functions prototype, and return values:
• Enumerations:
o Securable peripherals
typedef enum
{
HAL_{RIF/GTZC}_{RISC/RIMC/TZSC}_TIM2 = LL_{RIF/GTZC}_TIM2,
HAL_{RIF/GTZC}_{RISC/RIMC/TZSC}_UART4 = LL_{RIF/GTZC}_UART4,
HAL_{RIF/GTZC}_{RISC/RIMC/TZSC}_ETH1 = LL_{RIF/GTZC}_{RIMC}_ETH1,
...
} hal_{rif/gtzc}_{risc/rimc/tzsc}_periph_t;
o Security attributes
typedef enum
{
HAL_{RIF/GTZC}_NSEC = LL_{RIF/GTZC}_ATTR_NSEC,
HAL_{RIF/GTZC}_SEC = LL_{RIF/GTZC}_ATTR_SEC
} hal_{rif/gtzc}_sec_attr_t;
o Privilege attributes
typedef enum
{
HAL_{RIF/GTZC}_NPRIV = LL_{RIF/GTZC}_ATTR_NPRIV,
HAL_{RIF/GTZC}_PRIV = LL_{RIF/GTZC}_ATTR_PRIV
} hal_{rif/gtzc}_priv_attr_t;
o Lock status
typedef enum
{
HAL_{RIF/GTZC}_UNLOCKED = 0U,
HAL_{RIF/GTZC}_LOCKED = 1U
189

} hal_{rif/gtzc}_lock_status_t;
• Functions:
o Security and privilege attributes Set/Get functions
hal_status_t HAL_{RIF/GTZC}_{RISC/RIMC/TZSC}_SetPeriph{AttrName}Attr
(
hal_{rif/gtzc}_{risc/rimc/tzsc}_periph_t periph,
hal_{rif/gtzc}_{attrname}_attr_t attrname_attr
);
hal_{rif/gtzc}_{attrname}_attr_t HAL_{RIF/GTZC}_{RISC/RIMC/TZSC}_GetPeriph{AttrName}Attr
(hal_{rif/gtzc}_{risc/rimc/tzsc}_periph_t periph);
o Configuration lock function
hal_status_t HAL_{RIF/GTZC}_{RISC/RIMC/TZSC}_Lock{Periph}Config
(void/ hal_{rif/gtzc}_{risc/rimc/tzsc}_periph_t periph);
hal_{rif/gtzc}_lock_status_t HAL_{RIF/GTZC}_{RISC/RIMC/TZSC}_IsLocked{Periph}Config(void/
hal_{rif/gtzc}_{risc/rimc/tzsc}_periph_t periph);
▪ Note: depending from the HW implementation, the scope of the
configuration lock can be:
• Either applied to the whole block: in this case the above lock
functions does not take parameters (void) and the term {Periph}
is not inserted in the functions names.
• Either more granularity to lock the config for given
peripheral(s): in this case the function name takes {Periph} and
a parameter is given to precise the peripheral to apply the
configuration lock.
• Examples
typedef enum
{
HAL_RIF_RISC_TIM2 = LL_RIF_TIM2,
HAL_RIF_RISC_UART4 = LL_RIF_UART4,
...
} hal_rif_risc_periph_t;
typedef enum
{
HAL_RIF_NSEC = LL_RIF_ATTR_NSEC,
HAL_RIF_SEC = LL_RIF_ATTR_SEC
} hal_rif_sec_attr_t;
190

typedef enum
{
HAL_RIF_UNLOCKED = 0U, /*!< RIF configuration unlocked */
HAL_RIF_LOCKED = 1U /*!< RIF configuration locked */
} hal_rif_lock_status_t;
hal_status_t HAL_RIF_RISC_SetPeriphSecAttr(hal_rif_risc_periph_t periph,
hal_rif_sec_attr_t sec_attr);
hal_rif_sec_attr_t HAL_RIF_RISC_GetPeriphSecAttr(hal_rif_risc_periph_t periph);
hal_status_t HAL_RIF_RISC_LockPeriphConfig(hal_rif_risc_periph_t periph);
hal_rif_lock_status_t HAL_RIF_RISC_IsLockedPeriphConfig(hal_rif_risc_periph_t periph);
hal_status_t HAL_RIF_RIMC_LockConfig(void);
hal_status_t HAL_RIF_RISC_LockConfig(void);
hal_rif_lock_status_t HAL_RIF_RIMC_IsLockedConfig(void);
hal_rif_lock_status_t HAL_RIF_RISC_IsLockedConfig(void);
typedef enum
{
HAL_GTZC_TZSC_TIM2 = LL_GTZC_TIM2,
HAL_GTZC_TZSC_UART4 = LL_GTZC_UART4,
...
} hal_gtzc_tzsc_periph_t;
typedef enum
{
HAL_GTZC_NSEC = LL_GTZC_ATTR_NSEC,
HAL_GTZC_SEC = LL_GTZC_ATTR_SEC
} hal_gtzc_sec_attr_t;
typedef enum
{
HAL_GTZC_UNLOCKED = 0x00U, /*!< GTZC configuration unlocked */
HAL_GTZC_LOCKED = 0x01U /*!< GTZC configuration locked */
} hal_gtzc_lock_status_t;
hal_status_t HAL_GTZC_TZSC_SetPeriphSecAttr(hal_gtzc_tzsc_periph_t periph,
hal_gtzc_sec_attr_t sec_attr);
191

hal_gtzc_sec_attr_t HAL_GTZC_TZSC_GetPeriphSecAttr(hal_gtzc_tzsc_periph_t periph);
hal_status_t HAL_GTZC_TZSC_LockConfig(void);
hal_gtzc_lock_status_t HAL_GTZC_IsLockedConfig(void);
13.2.1.1.2. Security and privilege attribute APIs for block-based memories
(RIF_RISAB / GTZC_MPCBB)
• Enumerations:
o Block-based memories
typedef enum
{
HAL_{RIF/GTZC}_{RISAB/MPCBB}_{AXISRAM1/SRAM1} = LL_{RIF/GTZC}_{RISAB/MPCBB}_{AXISRAM1/SRAM1},
HAL_{RIF/GTZC}_{RISAB/MPCBB}_{AXISRAM2/SRAM2} = LL_{RIF/GTZC}_{RISAB/MPCBB}_{AXISRAM2/SRAM2},
HAL_{RIF/GTZC}_{RISAB/MPCBB}_{AXISRAM3/SRAM3} = LL_{RIF/GTZC}_{RISAB/MPCBB}_{AXISRAM3/SRAM3},
...
} hal_{rif/gtzc}_{risab/mpcbb}_memory_t;
o Secure to non-secure read/write access status
typedef enum
{
HAL_{RIF/GTZC}_{RISAB/MPCBB}_SEC_TO_NSEC_DISABLED = 0x00U,
HAL_{RIF/GTZC}_{RISAB/MPCBB}_SEC_TO_NSEC_ENABLED = 0x01U
} hal_{rif/gtzc}_{risab/mpcbb}_sec_to_nsec_access_status_t;
o Memory clock security state (feature available on GTZC only)
typedef enum
{
HAL_GTZC_MPCBB_CLK_SEC_NOT_INVERTED = LL_GTZC_MPCBB_CLK_SEC_NOT_INVERTED, /*!< GTZC clock
security not inverted */
HAL_GTZC_MPCBB_CLK_SEC_INVERTED = LL_GTZC_MPCBB_CLK_SEC_INVERTED /*!< GTZC clock
security inverted */
} hal_gtzc_mpcbb_clk_sec_state_t;
o Read/Write access status (feature available on RIF peripheral only)
typedef enum
{
HAL_RIF_{READ/WRITE}_DISABLED = LL_RIF_{READ/WRITE}_DISABLED,
HAL_RIF_{READ/WRITE}_ENABLED = LL_RIF_{READ/WRITE}_ENABLED
} hal_rif_{read/write}_access_status_t;
192

o RIF Illegal access status (feature available on RIF peripheral only)
typedef enum
{
HAL_RIF_ILAC_INACTIVE = 0x00U,
HAL_RIF_ILAC_ACTIVE = 0x01U
} hal_rif_ilac_status_t;
Note: this enumeration is used to return the illegal access status by both RIF_RISAB and
RISAF.
o RIF Illegal access read/write access
typedef enum
{
HAL_RIF_ILAC_READ = 0x00U,
HAL_RIF_ILAC_WRITE = 0x01U
} hal_rif_ilac_access_t;
• Structure
o RIF illegal access memory information structure (not applicable for GTZC)
typedef struct
{
hal_rif_ilac_access_t access;
uint32_t addr;
hal_rif_sec_attr_t sec;
hal_rif_priv_attr_t priv;
} hal_rif_ilac_memory_info_t;
Note: the same structure is for both RIF_RISAB and RIF_RISAF to provide the illegal access
info to a block based memory or to the config of a watermark memory.
• Functions:
o Security and privilege attributes Set/Get functions
hal_status_t HAL_{RIF/GTZC}_{RISAB/MPCBB}_Set{AttrName}Attr{ByBlock/ByAddr}
(
hal_{rif/gtzc}_{risab/mpcbb}_memory_t memory,
uint32_t {start_block/offset_byte}, uint32_t {block_nbr/size_byte},
hal_{rif/gtzc}_{attrname}_attr_t attrname_attr
);
hal_{rif/gtzc}_{attrname}_attr_t HAL_{RIF/GTZC}_{RISAB/MPCBB}_Get{AttrName}Attr{ByBlock/ByAddr}
(
hal_{rif/gtzc}_{risab/mpcbb}_memory_t memory,
uint32_t {block/offset_byte}
193

);
▪ Note: the same attribute enumeration hal_{rif/gtzc}_{attrname}_attr_t
described section “Security and privilege attribute APIs for securable
peripherals must be is used.
o Enabling and disabling secure to non-secure read/write access
hal_status_t HAL_{RIF/GTZC}_{RISAB/MPCBB}_EnableSecToNSecRdWrAccess
(hal_{rif/gtzc}_{risab/mpcbb}_memory_t memory);
hal_status_t HAL_{RIF/GTZC}_{RISAB/MPCBB}_DisableSecToNSecRdWrAccess
(hal_{rif/gtzc}_{risab/mpcbb}_memory_t memory);
hal_{rif/gtzc}_{risab/mpcbb}_sec_to_nsec_access_status_t
HAL_{RIF/GTZC}_{RISAB/MPCBB}_IsEnabledSecToNSecRdWrAccess
(hal_{rif/gtzc}_{risab/mpcbb}_memory_t memory);
o Set/Get block based memory clock security state (feature available on GTZC
only)
hal_status_t HAL_GTZC_MPCBB_SetClkSecStateInvertion(hal_gtzc_mpcbb_memory_t memory_id,
hal_gtzc_mpcbb_clk_sec_state_t clk_sec_state);
hal_gtzc_mpcbb_clk_sec_state_t HAL_GTZC_MPCBB_GetClkSecStateInvertion(hal_gtzc_mpcbb_memory_t memory);
o Configuration lock
hal_status_t HAL_{RIF/GTZC}_{RISAB/MPCBB}_LockConfig{ByPage/BySuperBlock/ByAddr}
(
hal_{rif/gtzc}_{risab/mpcbb}_memory_t memory,
uint32_t {start_page/start_super_blk/offset_byte}, uint32_t
{page_nbr/super_blk_nbr/size_byte}
);
hal_{rif/gtzc}_lock_status_t HAL_{RIF/GTZC}_{RISAB/MPCBB}_IsLockedConfig{ByPage/BySuperBlock/ByAddr}
(
hal_{rif/gtzc}_{risab/mpcbb}_memory_t memory,
uint32_t {page/super_blk/offset_byte}
);
▪ Note: the same lock status enumeration hal_{rif/gtzc}_lock_status_t
described section “Security and privilege attribute APIs for securable
peripherals must be is used
o Enable and disable read/write access (feature available on RIF peripheral only)
hal_status_t HAL_RIF_RISAB_{Enable/Disable}{Rd/Wr}Access{ByPage/ByAddr}
194

(
hal_rif_risab_memory_t memory,
uint32_t {start_page/offset_byte},
uint32_t {page_nbr/size_byte}
);
hal_rif_{read/write}_access_status_t HAL_RIF_RISAB_IsEnabled{Page/Addr}{rd/wr}Access
(
hal_rif_risab_memory_t memory,
uint32_t {page/offset_byte}
);
o Get Illegal access info (feature available on RIF peripheral only)
hal_rif_ilac_status_t HAL_RIF_RISAB_IsIllegalConfigAccess(hal_rif_risab_memory_t memory);
hal_rif_ilac_status_t HAL_RIF_RISAB_IsIllegalMemoryAccess(hal_rif_risab_memory_t memory);
void HAL_RIF_RISAB_GetIllegalMemoryAccessInfo(hal_rif_risab_memory_t memory,
hal_rif_ilac_memory_info_t *p_info);
• Examples
typedef enum
{
HAL_RIF_RISAB_AXISRAM1 = LL_RIF_RISAB_AXISRAM1,
HAL_RIF_RISAB_AXISRAM2 = LL_RIF_RISAB_AXISRAM2,
...
} hal_rif_risab_memory_t;
typedef enum
{
HAL_RIF_RISAB_SEC_TO_NSEC_DISABLED = 0x00U, /*!< RIF RISAB secure read/write data accesses
to non-secure blocks and pages disabled */
HAL_RIF_RISAB_SEC_TO_NSEC_ENABLED = 0x01U /*!< RIF RISAB secure read/write data accesses
to non-secure blocks and pages enabled */
} hal_rif_risab_sec_to_nsec_access_status_t;
hal_status_t HAL_RIF_RISAB_SetSecAttrByBlock(hal_rif_risab_memory_t memory,
uint32_t start_block,
uint32_t block_nbr,
hal_rif_sec_attr_t sec_attr);
hal_status_t HAL_RIF_RISAB_SetPrivAttrByBlock(hal_rif_risab_memory_t memory,
uint32_t start_block,
uint32_t block_nbr,
hal_rif_priv_attr_t priv_attr);
195

hal_rif_sec_attr_t HAL_RIF_RISAB_GetSecAttrByBlock(hal_rif_risab_memory_t memory,
uint32_t block);
hal_rif_priv_attr_t HAL_RIF_RISAB_GetPrivAttrByBlock(hal_rif_risab_memory_t memory,
uint32_t block);
hal_status_t HAL_RIF_RISAB_EnableSecToNSecRdWrAccess(hal_rif_risab_memory_t memory);
hal_status_t HAL_RIF_RISAB_DisableSecToNSecRdWrAccess(hal_rif_risab_memory_t memory);
hal_rif_risab_sec_to_nsec_access_status_t
HAL_RIF_RISAB_IsEnabledSecToNSecRdWrAccess(hal_rif_risab_memory_t memory);
hal_status_t HAL_RIF_RISAB_SetSecAttrByAddr(hal_rif_risab_memory_t memory,
uint32_t offset_byte,
uint32_t size_byte,
hal_rif_sec_attr_t sec_attr);
hal_status_t HAL_RIF_RISAB_SetPrivAttrByAddr(hal_rif_risab_memory_t memory,
uint32_t offset_byte,
uint32_t size_byte,
hal_rif_priv_attr_t priv_attr);
hal_rif_sec_attr_t HAL_RIF_RISAB_GetSecAttrByAddr(hal_rif_risab_memory_t memory,
uint32_t offset_byte);
hal_rif_priv_attr_t HAL_RIF_RISAB_GetPrivAttrByAddr(hal_rif_risab_memory_t memory,
uint32_t offset_byte);
hal_status_t HAL_RIF_RISAB_EnableRdAccessByPage(hal_rif_risab_memory_t memory,
uint32_t start_page,
uint32_t page_nbr);
hal_status_t HAL_RIF_RISAB_DisableRdAccessByPage(hal_rif_risab_memory_t memory,
uint32_t start_page,
uint32_t page_nbr);
hal_rif_read_access_status_t
HAL_RIF_RISAB_IsEnabledPageRdAccess(hal_rif_risab_memory_t memory,
uint32_t page);
hal_status_t HAL_RIF_RISAB_EnableWrAccessByPage(hal_rif_risab_memory_t memory,
uint32_t start_page,
uint32_t page_nbr);
hal_status_t HAL_RIF_RISAB_DisableWrAccessByPage(hal_rif_risab_memory_t memory,
196

uint32_t start_page,
uint32_t page_nbr);
hal_rif_write_access_status_t
HAL_RIF_RISAB_IsEnabledPageWrAccess(hal_rif_risab_memory_t memory,
uint32_t page);
hal_status_t HAL_RIF_RISAB_EnableRdAccessByAddr(hal_rif_risab_memory_t memory,
uint32_t offset_byte,
uint32_t size_byte);
hal_status_t HAL_RIF_RISAB_DisableRdAccessByAddr(hal_rif_risab_memory_t memory,
uint32_t offset_byte,
uint32_t size_byte);
hal_rif_read_access_status_t HAL_RIF_RISAB_IsEnabledAddrRdAccess(hal_rif_risab_memory_t
memory,
uint32_t offset_byte);
hal_status_t HAL_RIF_RISAB_EnableWrAccessByAddr(hal_rif_risab_memory_t memory,
uint32_t offset_byte,
uint32_t size_byte);
hal_status_t HAL_RIF_RISAB_DisableWrAccessByAddr(hal_rif_risab_memory_t memory,
uint32_t offset_byte,
uint32_t size_byte);
hal_rif_write_access_status_t
HAL_RIF_RISAB_IsEnabledAddrWrAccess(hal_rif_risab_memory_t memory,
uint32_t offset_byte);
typedef enum
{
HAL_GTZC_MPCBB_SRAM1 = (uint32_t)LL_GTZC_MPCBB_SRAM1,/*!< GTZC block based SRAM1 memory */
HAL_GTZC_MPCBB_SRAM2 = (uint32_t)LL_GTZC_MPCBB_SRAM2,/*!< GTZC block based SRAM2 memory */
#if defined (SRAM3_BASE)
HAL_GTZC_MPCBB_SRAM3 = (uint32_t)LL_GTZC_MPCBB_SRAM3,/*!< GTZC block based SRAM3 memory */
#endif /* SRAM3_BASE */
HAL_GTZC_MPCBB_SRAM4 = (uint32_t)LL_GTZC_MPCBB_SRAM4,/*!< GTZC block based SRAM4 memory */
#if defined (SRAM5_BASE)
HAL_GTZC_MPCBB_SRAM5 = (uint32_t)LL_GTZC_MPCBB_SRAM5,/*!< GTZC block based SRAM5 memory */
#endif /* SRAM5_BASE */
#if defined (SRAM6_BASE)
197

HAL_GTZC_MPCBB_SRAM6 = (uint32_t)LL_GTZC_MPCBB_SRAM6 /*!< GTZC block based SRAM6 memory */
#endif /* SRAM6_BASE */
} hal_gtzc_mpcbb_memory_t;
typedef enum
{
HAL_GTZC_MPCBB_SEC_TO_NSEC_DISABLED = 0x00U,
HAL_GTZC_MPCBB_SEC_TO_NSEC_ENABLED = 0x01U
} hal_gtzc_mpcbb_sec_to_nsec_access_status_t;
typedef enum
{
HAL_GTZC_MPCBB_CLK_SEC_NOT_INVERTED = LL_GTZC_MPCBB_CLK_SEC_NOT_INVERTED, /*!< GTZC clock
security not inverted */
HAL_GTZC_MPCBB_CLK_SEC_INVERTED = LL_GTZC_MPCBB_CLK_SEC_INVERTED /*!< GTZC clock
security inverted */
} hal_gtzc_mpcbb_clk_sec_state_t;
hal_status_t HAL_GTZC_MPCBB_SetSecAttrByBlock(hal_gtzc_mpcbb_memory_t memory,
uint32_t start_block,
uint32_t block_nbr,
hal_gtzc_sec_attr_t sec_attr);
hal_status_t HAL_GTZC_MPCBB_SetPrivAttrByBlock(hal_gtzc_mpcbb_memory_t memory,
uint32_t start_block,
uint32_t block_nbr,
hal_gtzc_priv_attr_t priv_attr);
hal_gtzc_sec_attr_t HAL_GTZC_MPCBB_GetSecAttrByBlock(hal_gtzc_mpcbb_memory_t memory,
uint32_t block);
hal_rif_priv_attr_t HAL_GTZC_MPCBB_GetPrivAttrByBlock(hal_gtzc_mpcbb_memory_t memory,
uint32_t block);
hal_status_t HAL_GTZC_MPCBB_EnableSecToNSecRdWrAccess(hal_gtzc_mpcbb_memory_t memory)
hal_status_t HAL_GTZC_MPCBB_DisableSecToNSecRdWrAccess(hal_gtzc_mpcbb_memory_t memory);
hal_gtzc_mpcbb_sec_to_nsec_access_status_t
HAL_GTZC_MPCBB_IsEnabledSecToNSecRdWrAccess(hal_gtzc_mpcbb_memory_t memor);
hal_status_t HAL_GTZC_MPCBB_SetClkSecStateInvertion(hal_gtzc_mpcbb_memory_t memory_id,
hal_gtzc_mpcbb_clk_sec_state_t clk_sec_state);
198

hal_gtzc_mpcbb_clk_sec_state_t
HAL_GTZC_MPCBB_GetClkSecStateInvertion(hal_gtzc_mpcbb_memory_t memory);
hal_status_t HAL_GTZC_MPCBB_LockConfigBySuperBlock(
hal_gtzc_mpcbb_memory_t memory,
uint32_t start_super_blk,
uint32_t super_blk_nbr
);
hal_gtzc_lock_status_t HAL_GTZC_MPCBB_IsLockedConfigBySuperBlock
(
hal_gtzc_mpcbb_memory_t memory,
uint32_t super_blk
);
hal_status_t HAL_GTZC_MPCBB_SetSecAttrByAddr(hal_gtzc_mpcbb_memory_t memory,
uint32_t offset_byte,
uint32_t size_byte,
hal_gtzc_sec_attr_t sec_attr);
hal_status_t HAL_GTZC_MPCBB_SetPrivAttrByAddr(hal_gtzc_mpcbb_memory_t memory,
uint32_t offset_byte,
uint32_t size_byte,
hal_rif_priv_attr_t priv_attr);
hal_gtzc_sec_attr_t HAL_GTZC_MPCBB_GetSecAttrByAddr(hal_gtzc_mpcbb_memory_t memory,
uint32_t offset_byte);
hal_gtzc_priv_attr_t HAL_RIF_RISAB_GetPrivAttrByAddr(hal_gtzc_mpcbb_memory_t memory,
uint32_t offset_byte);
13.2.1.1.3. Security and privilege attribute APIs for watermark memories
(RIF_RISAF/ GTZC_TZSC-MPCWM)
Notes:
▪ On The RIF-RISAF peripheral it is possible to define regions and
subregions. On the GTZC-MPCWM it is possible to define subregions
only.
▪ Enabling and disabling the read and write access is possible on the RIF-
RISAF peripheral only (not available on the GTZC- MPCWM). This
setting is possible by subregion.
199

▪ Locking the configuration is possible on both RIF-RISAF and GTZC-
MPCWM. This setting is possible by subregion.
▪ To generalize, for RIF both region and subregion variant of the below
APIs must be provided. For the GTZC only the variant of the API with
subregion must be provided, also in this GTZC case there is no “region”
parameter (see also next examples for RIF and GTZC).
• Enumerations:
o RIF_RISAF/GTZC_TZSC-MPCWM memories
typedef enum
{
HAL_{RIF/GTZC}_{RISAF/TZSC_MPCWM}_{XSPI1/OCTOSPI1} = LL_{RIF/GTZC}_{RISAF/TZSC_MPCWM}_{XSPI1/OCTOSPI1},
HAL_{RIF/GTZC}_{RISAF/TZSC_MPCWM}_{XSPI2/OCTOSPI2} = LL_{RIF/GTZC}_{RISAF/TZSC_MPCWM}_{XSPI2/OCTOSPI2},
...
} hal_{rif/gtzc}_{risaf/tzsc_mpcwm}_memory_t
o RIF_RISAF regions (not applicable for GTZC)
typedef enum
{
HAL_RIF_RISAF_REGION_1 = LL_RIF_RISAF_REGION_1, /*!< RIF RISAF region 1 */
HAL_RIF_RISAF_REGION_2 = LL_RIF_RISAF_REGION_2, /*!< RIF RISAF region 2 */
...
} hal_rif_risaf_region_t;
o RIF_RISAF/GTZC_TZSC-MPCWM subregions
typedef enum
{
HAL_{RIF/GTZC}_{RISAF/TZSC_MPCWM}_SUBREGION_A = LL_{RIF/GTZC}_{RISAF/TZSC_MPCWM}_SUBREGION_A,
HAL_{RIF/GTZC}_{RISAF/TZSC_MPCWM}_SUBREGION_B = LL_{RIF/GTZC}_{RISAF/TZSC_MPCWM}_SUBREGION_B
} hal_{rif/gtzc}_{risaf/tzsc_mpcwm}_subregion_t;
o RIF_RISAF/GTZC_TZSC-MPCWM Region and subregion enabled status
typedef enum
{
HAL_{RIF/GTZC}_{RISAF/TZSC_MPCWM}_{REGION/SUBREGION}_DISABLED = 0U,
HAL_{RIF/GTZC}_{RISAF/TZSC_MPCWM}_{REGION/SUBREGION}_ENABLED = 1U
} hal_{rif/gtzc}_{risaf/tzsc_mpcwm}_{region/subregion}_status_t;
• Functions:
o Defining the region or the subregion: Set/get boundaries
200

hal_status_t HAL_{RIF/GTZC}_{RISAF/TZSC_MPCWM}_Set{Region/SubRegion}Boundaries
(
hal_{rif/gtzc}_{risaf/tzsc_mpcwm}_memory_t memory,
hal_rif_risaf_region_t region, /* applicable for RIF only */
hal_{rif/gtzc}_{risaf/tzsc_mpcwm}_subregion_t subregion,
uint32_t offset_byte,
uint32_t size_byte
);
void HAL_{RIF/GTZC}_{RISAF/TZSC_MPCWM}_Get{Region/SubRegion}Boundaries
(
hal_{rif/gtzc}_{risaf/tzsc_mpcwm}_memory_t memory,
hal_rif_risaf_region_t region, /* applicable for RIF only */
hal_{rif/gtzc}_{risaf/tzsc_mpcwm}_subregion_t subregion,
uint32_t *offset_byte,
uint32_t *size_byte
);
▪ Note: For the RIF-RISAF peripheral, it is possible to define regions and
subregions. On the GTZC-MPCWM it is possible to define subregions
only. Thus:
• For RIF both region and subregion variant of the APIs must be
provided.
• For the GTZC only the variant of the API with subregion must
be provided, also in this GTZC case there is no “region”
parameter (see also next examples for RIF and GTZC).
o Set/get attributes for a region/subregion
hal_status_t HAL_{RIF/GTZC}_{RISAF/TZSC_MPCWM}_Set{Region/SubRegion}{AttrName}Attr
(
hal_{rif/gtzc}_{risaf/tzsc_mpcwm}_memory_t memory,
hal_rif_risaf_region_t region, /*applicable for RIF only*/
hal_{rif/gtzc}_{risaf/tzsc_mpcwm}_subregion_t subregion,
hal_{rif/gtzc}_{attrname}_attr_t attrname_attr
);
hal_{rif/gtzc}_{attrname}_attr_t attrname_attr
HAL_{RIF/GTZC}_{RISAF/TZSC_MPCWM}_Get{Region/SubRegion}{AttrName}Attr
(
hal_{rif/gtzc}_{risaf/tzsc_mpcwm}_memory_t memory,
hal_rif_risaf_region_t region, /*applicable for RIF only*/
hal_{rif/gtzc}_{risaf/tzsc_mpcwm}_subregion_t subregion
);
201

o Enable and disable read/write access for a subregion
▪ Note: Enabling and disabling the read and write access is possible on
the RIF-RISAF peripheral only (not available on the GTZC- MPCWM).
This setting is possible by subregion.
▪ The same enumeration “hal_rif_{read/write}_access_status_t” used in
RIF-RISAB is also used in RIF-RISAF to specify the read/write access
status)
hal_status_t HAL_RIF_RISAF_{Enable/Disable}SubRegion{Rd/Wr}Access
(
hal_rif_risaf_memory_t memory,
hal_rif_risaf_region_t region,
hal_rif_risaf_subregion_t subregion
);
hal_rif_{read/write}_access_status_t HAL_RIF_RISAF_IsEnabled{Rd/Wr}AccessSubRegion
(
hal_rif_risaf_memory_t memory,
hal_rif_risaf_region_t region,
hal_rif_risaf_subregion_t subregion
);
o Enable and disable a region/subregion
▪ Note: Same as above, on RIF both level region and subregion are
available (so both APIs level must be provided). On GTZC, only the
subregion level is possible, given so, only subregion APIs must be
provided.
hal_status_t HAL_{RIF/GTZC}_{RISAF/TZSC_MPCWM}_{Enable/Disable}{Region/SubRegion}
(
hal_{rif/gtzc}_{risaf/tzsc_mpcwm}_memory_t memory,
hal_rif_risaf_region_t region,
hal_{rif/gtzc}_{risaf/tzsc_mpcwm}_subregion_t subregion
);
hal_{rif/gtzc}_{risaf/tzsc_mpcwm}_{region/subregion}_status_t
HAL_{RIF/GTZC}_{RISAF/TZSC_MPCWM}_IsEnabled{Region/SubRegion}
(
hal_{rif/gtzc}_{risaf/tzsc_mpcwm}_memory_t memory,
hal_rif_risaf_region_t region,
hal_{rif/gtzc}_{risaf/tzsc_mpcwm}_subregion_t subregion
);
o Lock a subregion configuration:
202

▪ Note: Locking the configuration is possible on both RIF-RISAF and
GTZC-MPCWM. This setting is possible by subregion.
Hal_status_t HAL_{RIF/GTZC}_{RISAF/TZSC_MPCWM}_Lock{SubRegion}Config
(
hal_{rif/gtzc}_{risaf/tzsc_mpcwm}_memory_t memory,
hal_rif_risaf_region_t region,
hal_{rif/gtzc}_{risaf/tzsc_mpcwm}_subregion_t subregion
);
hal_{rif/gtzc}_lock_status_t
HAL_{RIF/GTZC}_{RISAF/TZSC_MPCWM}_IsLocked{SubRegion}Config
(
hal_{rif/gtzc}_{risaf/tzsc_mpcwm}_memory_t memory,
hal_rif_risaf_region_t region,
hal_{rif/gtzc}_{risaf/tzsc_mpcwm}_subregion_t subregion
);
Note: the same lock status enumeration “hal_{rif/gtzc}_lock_status_t” described section
“Security and privilege attribute APIs for securable peripherals” must be is used to describe
the lock status.
o RIF_RISAF, illegal access, status and information functions (not possible on
GTZC):
hal_rif_ilac_status_t HAL_RIF_RISAF_IsIllegalConfigAccess(hal_rif_risaf_memory_t memory);
hal_rif_ilac_status_t HAL_RIF_RISAF_IsIllegalMemoryAccess(hal_ rif_risaf_memory_t memory);
void HAL_RIF_RISAF_GetIllegalMemoryAccessInfo(hal_ rif_risaf_memory_t memory,
hal_rif_ilac_memory_info_t *p_info);
Notes: The same enumeration “hal_rif_ilac_status_t” and structure
“hal_rif_ilac_memory_info_t “ described in section “Security and privilege attribute APIs for
block-based memories (RIF_RISAB / GTZC_MPCBB)” are used for both RIF_RISAB and
RIF_RISAF.
• Examples
typedef enum
{
HAL_RIF_RISAF_XSPI1 = LL_RIF_RISAF_XSPI1,
HAL_RIF_RISAF_XSPI2 = LL_RIF_RISAF_XSPI2,
HAL_RIF_RISAF_FMC = LL_RIF_RISAF_FMC,
HAL_RIF_RISAF_BKPRAM = LL_RIF_RISAF_BKPRAM
} hal_rif_risaf_memory_t;
typedef enum
{
203

HAL_RIF_RISAF_REGION_1 = LL_RIF_RISAF_REGION_1,
..
HAL_RIF_RISAF_REGION_7 = LL_RIF_RISAF_REGION_7
} hal_rif_risaf_region_t;
typedef enum
{
HAL_RIF_RISAF_SUBREGION_A = LL_RIF_RISAF_SUBREGION_A,
HAL_RIF_RISAF_SUBREGION_B = LL_RIF_RISAF_SUBREGION_B
} hal_rif_risaf_subregion_t;
typedef enum
{
HAL_RIF_RISAF_REGION_DISABLED = 0x00U,
HAL_RIF_RISAF_REGION_ENABLED = 0x01U
} hal_rif_risaf_region_status_t;
typedef enum
{
HAL_RIF_RISAF_SUBREGION_DISABLED = 0x00U,
HAL_RIF_RISAF_SUBREGION_ENABLED = 0x01U
} hal_rif_risaf_subregion_status_t;
hal_status_t HAL_RIF_RISAF_SetRegionBoundaries(hal_rif_risaf_memory_t memory,
hal_rif_risaf_region_t region,
uint32_t offset_byte, uint32_t size_byte);
void HAL_RIF_RISAF_GetRegionBoundaries(hal_rif_risaf_memory_t memory,
hal_rif_risaf_region_t region,
uint32_t *offset_byte,
uint32_t *size_byte);
hal_status_t HAL_RIF_RISAF_SetSubRegionBoundaries(hal_rif_risaf_memory_t memory,
hal_rif_risaf_region_t region,
hal_rif_risaf_subregion_t subregion,
uint32_t offset_byte,
uint32_t size_byte);
void HAL_RIF_RISAF_GetSubRegionBoundaries(hal_rif_risaf_memory_t memory,
hal_rif_risaf_region_t region,
hal_rif_risaf_subregion_t subregion,
uint32_t *offset_byte,
uint32_t *size_byte);
204

hal_status_t HAL_RIF_RISAF_SetRegionSecAttr(hal_rif_risaf_memory_t memory,
hal_rif_risaf_region_t region,
hal_rif_sec_attr_t sec_attr);
hal_status_t HAL_RIF_RISAF_SetRegionPrivAttr(hal_rif_risaf_memory_t memory,
hal_rif_risaf_region_t region,
hal_rif_priv_attr_t priv_attr);
hal_rif_sec_attr_t HAL_RIF_RISAF_GetRegionSecAttr(hal_rif_risaf_memory_t memory,
hal_rif_risaf_region_t region);
hal_rif_priv_attr_t HAL_RIF_RISAF_GetRegionPrivAttr(hal_rif_risaf_memory_t memory,
hal_rif_risaf_region_t region);
hal_status_t HAL_RIF_RISAF_SetSubRegionSecAttr(hal_rif_risaf_memory_t memory,
hal_rif_risaf_region_t region,
hal_rif_risaf_subregion_t subregion,
hal_rif_sec_attr_t sec_attr);
hal_status_t HAL_RIF_RISAF_SetSubRegionPrivAttr(hal_rif_risaf_memory_t memory,
hal_rif_risaf_region_t region,
hal_rif_risaf_subregion_t subregion,
hal_rif_priv_attr_t priv_attr);
hal_rif_sec_attr_t HAL_RIF_RISAF_GetSubRegionSecAttr(hal_rif_risaf_memory_t memory,
hal_rif_risaf_region_t region,
hal_rif_risaf_subregion_t subregion);
hal_rif_priv_attr_t HAL_RIF_RISAF_GetSubRegionPrivAttr(hal_rif_risaf_memory_t memory,
hal_rif_risaf_region_t region,
hal_rif_risaf_subregion_t subregion);
hal_status_t HAL_RIF_RISAF_EnableSubRegionWrAccess(hal_rif_risaf_memory_t memory,
hal_rif_risaf_region_t region,
hal_rif_risaf_subregion_t subregion);
hal_status_t HAL_RIF_RISAF_DisableSubRegionWrAccess(hal_rif_risaf_memory_t memory,
hal_rif_risaf_region_t region,
hal_rif_risaf_subregion_t subregion);
hal_status_t HAL_RIF_RISAF_EnableSubRegionRdAccess(hal_rif_risaf_memory_t memory,
hal_rif_risaf_region_t region,
hal_rif_risaf_subregion_t subregion);
hal_status_t HAL_RIF_RISAF_DisableSubRegionRdAccess(hal_rif_risaf_memory_t memory,
205

hal_rif_risaf_region_t region,
hal_rif_risaf_subregion_t subregion);
hal_rif_write_access_status_t
HAL_RIF_RISAF_IsEnabledWrAccessSubRegion(hal_rif_risaf_memory_t memory,
hal_rif_risaf_region_t region,
hal_rif_risaf_subregion_t subregion);
hal_rif_read_access_status_t HAL_RIF_RISAF_IsEnabledRdAccessSubRegion (
hal_rif_risaf_memory_t memory,
hal_rif_risaf_region_t region,
hal_rif_risaf_subregion_t subregion);
hal_status_t HAL_RIF_RISAF_EnableRegion(
hal_rif_risaf_memory_t memory,
hal_rif_risaf_region_t region);
hal_status_t HAL_RIF_RISAF_DisableRegion(hal_rif_risaf_memory_t memory,
hal_rif_risaf_region_t region);
hal_rif_risaf_region_status_t HAL_RIF_RISAF_IsEnabledRegion(hal_rif_risaf_memory_t memory,
hal_rif_risaf_region_t region);
hal_status_t HAL_RIF_RISAF_EnableSubRegion(hal_rif_risaf_memory_t memory,
hal_rif_risaf_region_t region,
hal_rif_risaf_subregion_t subregion);
hal_status_t HAL_RIF_RISAF_DisableSubRegion(hal_rif_risaf_memory_t memory,
hal_rif_risaf_region_t region,
hal_rif_risaf_subregion_t subregion);
hal_rif_risaf_subregion_status_t HAL_RIF_RISAF_IsEnabledSubRegion(
hal_rif_risaf_memory_t memory,
hal_rif_risaf_region_t region,
hal_rif_risaf_subregion_t subregion);
hal_status_t HAL_RIF_RISAF_LockSubRegionConfig(hal_rif_risaf_memory_t memory,
hal_rif_risaf_region_t region,
hal_rif_risaf_subregion_t subregion);
hal_rif_lock_status_t HAL_RIF_RISAF_IsLockedSubRegionConfig(hal_rif_risaf_memory_t memory,
hal_rif_risaf_region_t region,
hal_rif_risaf_subregion_t
subregion);
206

hal_rif_ilac_status_t HAL_RIF_RISAF_IsIllegalConfigAccess(hal_rif_risaf_memory_t memory);
hal_rif_ilac_status_HAL_RIF_RISAF_IsIllegalMemoryAccess(hal_rif_risaf_memory_t memory);
void HAL_RIF_RISAF_GetIllegalMemoryAccessInfo(hal_rif_risaf_memory_t memory,
hal_rif_ilac_memory_info_t *p_info);
typedef enum
{
HAL_GTZC_TZSC_MPCWM_XSPI1 = LL_GTZC_TZSC_MPCWM_XSPI1,
HAL_GTZC_TZSC_MPCWM_XSPI2 = LL_GTZC_TZSC_MPCWM_XSPI2,
...
} hal_gtzc_tzsc_mpcwm_memory_t
typedef enum
{
HAL_GTZC_TZSC_MPCWM_SUBREGION_A = LL_GTZC_TZSC_MPCWM_SUBREGION_A,
HAL_GTZC_TZSC_MPCWM_SUBREGION_B = LL_GTZC_TZSC_MPCWM_SUBREGION_B
} hal_gtzc_tzsc_mpcwm_subregion_t;
typedef enum
{
HAL_GTZC_TZSC_MPCWM_SUBREGION_DISABLED = 0x00U,
HAL_GTZC_TZSC_MPCWM_SUBREGION_ENABLED = 0x01U
} hal_gtzc_tzsc_mpcwm_subregion_status_t;
hal_status_t HAL_GTZC_TZSC_MPCWM_SetSubRegionBoundaries(
hal_gtzc_tzsc_mpcwm_memory_t memory,
hal_gtzc_tzsc_mpcwm_subregion_t subregion,
uint32_t offset_byte,
uint32_t size_byte);
void HAL_GTZC_TZSC_MPCWM_GetSubRegionBoundaries(hal_gtzc_tzsc_mpcwm_memory_t memory,
hal_gtzc_tzsc_mpcwm_subregion_t subregion,
uint32_t *offset_byte,
uint32_t *size_byte);
hal_status_t HAL_GTZC_TZSC_MPCWM_SetSubRegionSecAttr(
hal_gtzc_tzsc_mpcwm_memory_t memory,
hal_gtzc_tzsc_mpcwm_subregion_t subregion,
hal_gtzc_sec_attr_t sec_attr);
hal_gtzc_sec_attr_t HAL_GTZC_TZSC_MPCWM_GetSubRegionSecAttr(
207

hal_gtzc_tzsc_mpcwm_memory_t memory,
hal_gtzc_tzsc_mpcwm_subregion_t subregion);
hal_status_t HAL_GTZC_TZSC_MPCWM_SetSubRegionPrivAttr(
hal_gtzc_tzsc_mpcwm_memory_t memory,
hal_gtzc_tzsc_mpcwm_subregion_t subregion,
hal_gtzc_priv_attr_t sec_attr);
hal_gtzc_priv_attr_t HAL_GTZC_TZSC_MPCWM_GetSubRegionPrivAttr(
hal_gtzc_tzsc_mpcwm_memory_t memory,
hal_gtzc_tzsc_mpcwm_subregion_t subregion);
hal_status_t HAL_GTZC_TZSC_MPCWM_EnableSubRegion(hal_gtzc_tzsc_mpcwm_memory_t memory,
hal_gtzc_tzsc_mpcwm_region_t region,
hal_gtzc_tzsc_mpcwm_subregion_t subregion);
hal_status_t HAL_GTZC_TZSC_MPCWM_DisableSubRegion(
hal_gtzc_tzsc_mpcwm_memory_t memory,
hal_gtzc_tzsc_mpcwm_region_t region,
hal_gtzc_tzsc_mpcwm_subregion_t subregion);
hal_gtzc_tzsc_mpcwm_subregion_status_t HAL_GTZC_TZSC_MPCWM_IsEnabledSubRegion(
hal_gtzc_tzsc_mpcwm_memory_t memory,
hal_gtzc_tzsc_mpcwm_region_t region,
hal_gtzc_tzsc_mpcwm_subregion_t subregion);
13.2.1.1.4. Illegal access
The illegal access detection feature applies upon any security illegal access: i.e for
RIF/GTZC aware peripherals, securable peripherals, Block based and watermark.
• Enumerations:
o Illegal access peripherals
typedef enum
{
HAL_{RIF/GTZC}_{IAC/TZIC}_TIM2 = LL_{RIF/GTZC}_TIM2,
HAL_{RIF/GTZC}_{IAC/TZIC}_UART4 = LL_{RIF/GTZC}_UART4,
HAL_{RIF/GTZC}_{IAC/TZIC}_ETH1 = LL_{RIF/GTZC}_{RIMC}_ETH1,
...
} hal_{rif/gtzc}_{iac/tzic}_periph_t;
o Illegal access interrupt status
typedef enum
{
208

HAL_{RIF/GTZC}_{IAC/TZIC}_IT_DISABLED = 0U,
HAL_{RIF/GTZC}_{IAC/TZIC}_IT_ENABLED = 1U
} hal_{rif/gtzc}_{iac/tzic}_it_status_t;
• Functions:
o Illegal access interrupts managements (enable/disable, IRQ handler and
callback)
void HAL_{RIF/GTZC}_{IAC/TZIC}_EnableIT(hal_{rif/gtzc}_{iac/tzic}_periph_t periph);
void HAL_{RIF/GTZC}_{IAC/TZIC}_DisableIT(hal_{rif/gtzc}_{iac/tzic}_periph_t periph);
hal_{rif/gtzc}_{iac/tzic}_it_status_t HAL_{RIF/GTZC}_{IAC/TZIC}_IsEnabledIT(
hal_{rif/gtzc}_{iac/tzic}_periph_t periph);
void HAL_{RIF/GTZC}_{IAC/TZIC}_IRQHandler(void);
void HAL_{RIF/GTZC}_{IAC/TZIC}_Callback(hal_{rif/gtzc}_{iac/tzic}_periph_t periph);
• Examples:
typedef enum
{
HAL_RIF_IAC_TIM2 = LL_RIF_TIM2,
...
} hal_rif_iac_periph_t;
typedef enum
{
HAL_RIF_IAC_IT_DISABLED = 0U,
HAL_RIF_IAC_IT_ENABLED = 1U
} hal_rif_iac_it_status_t;
hal_status_t HAL_RIF_IAC_EnableIT(hal_rif_iac_periph_t periph);
hal_status_t HAL_RIF_IAC_DisableIT(hal_rif_iac_periph_t periph);
hal_rif_iac_it_status_t HAL_RIF_IAC_IsEnabledIT(hal_rif_iac_periph_t periph);
void HAL_RIF_IAC_IRQHandler(void);
void HAL_RIF_IAC_Callback(hal_rif_iac_periph_t periph);
typedef enum
{
HAL_GTZC_TZIC_TIM2 = LL_GTZC_TIM2,
...
} hal_gtzc_tzic_periph_t;
209

typedef enum
{
HAL_GTZC_TZIC_IT_DISABLED = 0U,
HAL_GTZC_TZIC_IT_ENABLED = 1U
} hal_gtzc_tzic_it_status_t;
hal_status_t HAL_GTZC_TZIC_EnableIT(hal_gtzc_tzic_periph_t periph);
hal_status_t HAL_GTZC_TZIC_DisableIT(hal_gtzc_tzic_periph_t periph);
hal_gtzc_tzic_it_status_t HAL_GTZC_TZIC_IsEnabledIT(hal_gtzc_tzic_periph_t periph);
void HAL_GTZC_TZIC_IRQHandler(void);
void HAL_GTZC_TZIC_Callback(hal_gtzc_tzic_periph_t periph);
13.2.2. HAL and LL RIF-aware/TZ-aware peripherals APIs
The HAL and LL layers must include TrustZone (TZ)-aware and RIF-aware PPP attribute
management functions, with each TZ-aware/RIF-aware PPP LL HAL and LL module providing
its own attribute management APIs.
Attribute management must be provided as standalone. The RIF-aware/TZ-aware HAL PPP
attribute APIs must be callable independently of the HAL PPP handle initialization, with the
HAL PPP instance as the first parameter replacing the traditional handle parameter. See also
paragraph “HAL PPP instance retrieving” to understand how to get the PPP peripheral instance
from the HAL PPP handle.
Attribute functions must be unified across TZ-aware modules and families, and when possible,
between RIF and TZ implementations.
Items (such as PVD and WKUPPIN) must be clearly separated from their attributes
(Secure/NSecure).
Except the attribute setting functions, No other HAL nor LL function within any module must
impact the configured TZ/RIF attributes, ensuring system integrity. Function usage must support
both static configurations aligned with Trusted Execution Environment requirements (also
called isolation) and dynamic reconfiguration to adjust attributes according to application needs.
210

In the application code, when the RIF-aware/TZ-aware HAL/LL PPP attribute
functions are called statically (i.e. from the isolation part) then it must use
directly the needed instance.
// Using LL driver
LL_PPP_Func(PPPn, ...);
// Using HAL driver
HAL_PPP_Func(HAL_PPPn, ...);
When these functions are called dynamically (to reconfigure/adjust the
attributes according to the application needs), the application must use the
appropriate function to retrieve the instance from the handle (if the given driver
use a handle) and use it to call the attribute function.
// Using LL driver
LL_PPP_Func(HAL_PPP_GetLLInstance(hppp), ...);
// Using HAL driver
HAL_PPP_Func(HAL_PPP_GetInstance(hppp), ...);
13.2.2.1.1. LL RIF-aware/TZ-aware peripherals APIs
_STATIC_INLINE void LL_{PPP}_{SUBBLOCK}_Set{AttrName}Attr(
{PPP_TypeDef *pppx},
{uint32_t Items/subinstances},
uint32_t {attrname}_attr);
__STATIC_INLINE uint32_t LL_{PPP}_{SUBBLOCK}_Get{AttrName}Attr(
{PPP_TypeDef *pppx},
{uint32_t Item/subinstance);
__STATIC_INLINE void LL_{PPP}_{SUBBLOCK}_Lock{AttrName}Attr(
{PPP_TypeDef *pppx},
{uint32_t Items/subinstances});
__STATIC_INLINE void LL_{PPP}_{SUBBLOCK}_UnLock{AttrName}Attr(
{PPP_TypeDef *pppx},
{uint32_t Items/subinstances});
__STATIC_INLINE uint32_t LL_{PPP}_{SUBBLOCK}_IsLocked{AttrName}Attr(
{PPP_TypeDef *pppx},
{uint32_t Item/subinstance});
With:
211

• The {PPP} is the name of the peripheral.
• The {SUBBLOCK} (when existing) within a TZ-aware/RIF-aware LL module, it
must be applied within set/get attributes APIs.
• The {AttrName} is the attribute abbreviation described here:
• Sec, Priv, Public
• pppx is:
• The physical instance of type “PPP_TypeDef*” when existing in the given
driver (eg: LL FLASH)
• Omitted when the given HAL driver doesn’t use instance like the LL RCC or
PWR
•
Items/subinstances:
• Use subinstances when the attribute applies to sub-instances meaning multiple
identical resources of the same peripherals (e.g. , pins in case of the GPIO). In
this case these APIs reuse the already existing subinstances naming and
definitions (e.g. in case of gpio, subinstances = pins and must be set to the
defines LL_GPIO_PIN_n)
• Use items when the attribute applies to heterogeneous/specific parts of the
given peripheral instance (e.g the RCC oscillators and PLLs and other items).
In this case a set of dedicated defines is provided to list these items with the
following naming rules LL_{PPP}_{ATTRNAME}_ITEM_{ITEM}
LL_{PPP}_{ATTRNAME}_ITEM_ALL being required)
• Omitted when the attributes setting or lock apply to the given PPP instance. In
this case only the “pppx” instance is used if the LL driver already use it, if not
the function becomes “void”.
Notes:
• Set attributes APIs can be applied for one or several items/ subinstances (defines can
be ored/combined when possible).
• Get attributes APIs must be applied for one single item/ subinstance (Cannot be
ored/combined).
• Lock/Unlock/IsLocked APIs parameters (instance , items/subinstances) must be
aligned with:
o The given LL driver: whether it uses PPP_TypeDef instance or not (case of the
RCC)
o The given device capability (whether the lock can be performed by the instance
granularity or by item/sub-instance granularity)
• The unlock function must be provided only if it is possible to unlock “on the fly” (i.e
without the need of system reset)
• The IsLocked API must return the numerical value “1” when locked and “0” when
locked (same as all other LL_PPP_Isxxx APIs)
Examples:
RCC:
#define LL_RCC_ATTR_NSEC 0UL
212

#define LL_RCC_ATTR_SEC 1UL
#define LL_RCC_ATTR_NPRIV 0UL
#define LL_RCC_ATTR_PRIV 1UL
#define LL_RCC_ATTR_NPUBLIC 0UL
#define LL_RCC_ATTR_PUBLIC 1UL
#define LL_RCC_SEC_ITEM_HSE RCC_SECCFGR_HSE
...
#define LL_RCC_SEC_ITEM_PERIPHCLK RCC_SECCFGR_PER
#define LL_RCC_SEC_ITEM_ALL RCC_SECURE_MASK
#define LL_RCC_PRIV_ITEM_SYSCLK RCC_PRIVCFGR_SYS
...
#define LL_RCC_PRIV_ITEM_PERIPHCLK RCC_PRIVFGR_PERRIPH
#define LL_RCC_PRIV_ITEM_ALL RCC_PRIVRE_MASK
#define LL_RCC_LOCK_ITEM_RESET_FLAGS RCC_RCFGLOCKR_RMVF
...
#define LL_RCC_LOCK_ITEM_PERIPHCLK RCC_RCFGLOCKR_PERRIPH
#define LL_RCC_LOCK_ITEM_ALL RCC_PRIVRE_MASK
__STATIC_INLINE void LL_RCC_SetSecAttr(uint32_t item, uint32_t sec_attr)
__STATIC_INLINE uint32_t LL_RCC_GetSecAttr(uint32_t item)
__STATIC_INLINE void LL_RCC_SetPrivAttr(uint32_t item, uint32_t priv_attr)
__STATIC_INLINE uint32_t LL_RCC_GetPrivAttr(uint32_t item)
__STATIC_INLINE void LL_RCC_LockAttr(uint32_t item)
__STATIC_INLINE uint32_t LL_RCC_IsLockedAttr(uint32_t item)
Notes: in this LL RCC example:
• The instance is omitted as it is not used in the LL RCC driver
• Use items as the attributes setting applies to heterogenous parts (not identical) of the
RCC like the HSE, LSE…
• The lock is possible by item in the above example.
• No unlock API is provided as the unlock is not possible (unlock is done by system
reset)
GPIO:
#define LL_GPIO_PIN_0 GPIO_BSRR_BS0 /*!< Select pin 0 */
#define LL_GPIO_PIN_1 GPIO_BSRR_BS1 /*!< Select pin 1 */
...
#define LL_GPIO_PIN_14 GPIO_BSRR_BS14 /*!< Select pin 14 */
#define LL_GPIO_PIN_15 GPIO_BSRR_BS15 /*!< Select pin 15 */
#define LL_GPIO_PIN_ALL
#define LL_GPIO_ATTR_NSEC 0U /*!< I/O pin is nonsecure */
#define LL_GPIO_ATTR_SEC GPIO_SECCFGR_SEC0 /*!< I/O pin is secure */
#define LL_GPIO_ATTR_NPRIV 0U /*!< I/O pin is unprivileged */
213

#define LL_GPIO_ATTR_PRIV GPIO_PRIVCFGR_PRIV0 /*!< I/O pin is privileged */
__STATIC_INLINE void LL_GPIO_SetSecAttr(GPIO_TypeDef *gpiox,
uint32_t pin_mask,
uint32_t sec_attr)
__STATIC_INLINE uint32_t LL_GPIO_GetSecAttr(const GPIO_TypeDef *gpiox,
uint32_t pin)
__STATIC_INLINE void LL_GPIO_SetPrivAttr(GPIO_TypeDef *gpiox,
uint32_t pin_mask,
uint32_t priv_attr)
__STATIC_INLINE uint32_t LL_GPIO_GetPrivAttr(const GPIO_TypeDef *gpiox,
uint32_t pin)
__STATIC_INLINE void LL_GPIO_LockAttr(GPIO_TypeDef *gpiox, uint32_t pin_mask)
__STATIC_INLINE uint32_t LL_GPIO_IsLockedAttr(const GPIO_TypeDef *gpiox, uint32_t pin)
Notes: in this LL GPIO example the attributes APIs use:
• The GPIO_TypeDef instance: the port.
• The subinstances are the pins and using the same defines LL_GPIO_PIN_n as the
overall driver
• The attributes lock can be done by pin(s) in the above example.
• The attributes IsLocked API return the numerical values “0” or “1”.
EXTI:
#define LL_EXTI_LINE_0 EXTI_IMR1_IM0 /*!< Extended line 0 */
..
#define LL_EXTI_LINE_31 EXTI_IMR1_IM31 /*!< Extended line 31 */
#define LL_EXTI_LINE_ALL_0_31 EXTI_IMR1_IM_ALL /*!< All extended lines */
#define LL_EXTI_LINE_32 EXTI_IMR2_IM32 /*!< Extended line 32 */
..
#define LL_EXTI_LINE_63 EXTI_IMR2_IM63 /*!< Extended line 63 */
#define LL_EXTI_LINE_ALL_32_63 EXTI_IMR2_IM_ALL /*!< All extended lines */
#define LL_EXTI_ATTR_NSEC 0U
#define LL_EXTI_ATTR_SEC 1U
#define LL_EXTI_ATTR_NPRIV 0U
#define LL_EXTI_ATTR_PRIV 1U
/** @param exti_line This parameter can be a combination of the following values:
* @arg @ref LL_EXTI_LINE_0
* @arg @ref LL_EXTI_LINE_1
* ...
* @arg @ref LL_EXTI_LINE_25
*/
__STATIC_INLINE void LL_EXTI_SetSecAttr_0_31(uint32_t exti_line, uint32_t sec_attr)
/** @param exti_line This parameter can be one of the following values:
* @arg @ref LL_EXTI_LINE_0
214

* @arg @ref LL_EXTI_LINE_1
* ...
* @arg @ref LL_EXTI_LINE_31
*/
__STATIC_INLINE uint32_t LL_EXTI_GetSecAttr_0_31(uint32_t exti_line)
/** @param exti_line This parameter can be a combination of the following values:
* @arg @ref LL_EXTI_LINE_32
* @arg @ref LL_EXTI_LINE_1
* ...
* @arg @ref LL_EXTI_LINE_63
*/
__STATIC_INLINE void LL_EXTI_SetSecAttr_32_63(uint32_t exti_line, uint32_t sec_attr)
/** @param exti_line This parameter can be one of the following values:
* @arg @ref LL_EXTI_LINE_32
* @arg @ref LL_EXTI_LINE_1
* ...
* @arg @ref LL_EXTI_LINE_63
*/
__STATIC_INLINE uint32_t LL_EXTI_GetSecAttr_32_63(uint32_t exti_line)
/* same for the SetPrivAttr/GetPrivAttr APIs */
__STATIC_INLINE void LL_EXTI_LockLAttr(void)
__STATIC_INLINE uint32_t LL_EXTI_IsLockedAttr(void) /* return numerial values 0 or 1 */
Notes: in this LL EXTI example, the attributes APIs:
• Does not use the instance EXTI_TypeDef (same as the reset of this driver)
• The subinstance uses the defines LL_EXTI_LINE_n as the reset of the LL EXTI
driver. These lines can be combined (Ored) for the “Set” APIs but not for the “Get”
• The lock/IsLocked functions are void in the above example as the given HW EXTI
peripheral allows to lock all the lines attributes together (not possible to lock
individually the attributes of a given line)
• The IsLocked API return the numerical values “0” or “1”.
NVM:
#define LL_NVM_ATTR_NSEC 0UL
#define LL_NVM_ATTR_SEC 1UL
#define LL_NVM_ATTR_NPRIV 0UL
#define LL_NVM_ATTR_PRIV 1UL
#define LL_NVM_SEC_ITEM_PM NVM_SECCFGR_PM
#define LL_NVM_SEC_ITEM_PERF NVM_SECCFGR_PERF
..
#define LL_NVM_SEC_ITEM_ALL ..
#define LL_NVM_PRIV_ITEM_PM NVM_PRIVCFGR_PM
..
#define LL_NVM_PRIV_ITEM_ALL ..
#define LL_NVM_LOCK_ITEM_PM NVM_RCFGLOCKR_PM
..
215

#define LL_NVM_LOCK_ITEM_ALL ..
__STATIC_INLINE void LL_NVM_SetSecAttr(NVM_TypeDef *nvmx,
uint32_t item,
uint32_t sec_attr)
__STATIC_INLINE uint32_t LL_NVM_GetSecAttr(const NVM_TypeDef *nvmx, uint32_t item)
__STATIC_INLINE void LL_NVM_SetPrivAttr(NVM_TypeDef *nvmx,
uint32_t items,
uint32_t priv_attr)
__STATIC_INLINE uint32_t LL_NVM_GetPrivAttr(const NVM_TypeDef *nvmx, uint32_t item)
__STATIC_INLINE void LL_NVM_LockAttr(NVM_TypeDef *nvmx, uint32_t items)
__STATIC_INLINE uint32_t LL_NVM_IsLockedAttr(const NVM_TypeDef *nvmx, uint32_t item)
Notes: in this LL NVM example, the attributes APIs use:
• The existing instance of type “NVM_TypeDef“
• items as the attributes setting applies to heterogenous parts (not identical) of the
NVM. The items can be combined for the “Set” and “Lock” APIs. Not for the
“Get”/”IsLocked” APIs.
• The IsLocked API returns the numerical values “0” or “1”.
DMA:
#define LL_DMA_CHANNEL_0 0x01UL
#define LL_DMA_CHANNEL_1 0x02UL
...
#define LL_DMA_CHANNEL_15 0x8000UL
#define LL_DMA_CHANNEL_ALL 0xFFFFUL
/* Channel security items */
#define LL_DMA_SEC_ITEM_SRC DMA_CTR1_SSEC
#define LL_DMA_SEC_ITEM_DEST DMA_CTR1_DSEC
#define LL_DMA_SEC_ITEM_ALL (DMA_CTR1_SSEC| DMA_CTR1_DSEC)
#define LL_DMA_ATTR_NSEC 0U
#define LL_DMA_ATTR_SEC 1U
#define LL_DMA_ATTR_NPRIV 0U
#define LL_DMA_ATTR_PRIV 1U
/** @param channel This parameter can be a combination of the following values:
* @arg @ref LL_DMA_CHANNEL_0
* ...
* @arg @ref LL_DMA_CHANNEL_15
*/
__STATIC_INLINE void LL_DMA_SetSecAttr(DMA_TypeDef *dma,
uint32_t channel,
uint32_t sec_attr)
/** @param channel This parameter can be one of the following values:
* @arg @ref LL_DMA_CHANNEL_0
* ...
216

* @arg @ref LL_DMA_CHANNEL_15
*/
__STATIC_INLINE uint32_t LL_DMA_GetSecAttr(DMA_TypeDef *dma, uint32_t channel)
/* same for the SetPrivAttr/GetPrivAttr APIs */
__STATIC_INLINE void LL_DMA_LockAttr(DMA_TypeDef *dma, uint32_t channel)
/** @param channel This parameter can be one of the following values:
* @arg @ref LL_DMA_CHANNEL_0
* ...
* @arg @ref LL_DMA_CHANNEL_15
* @retval attribute lock status (1 or 0).
*/
__STATIC_INLINE uint32_t LL_DMA_IsLockedAttr(DMA_TypeDef *dma, uint32_t channel)
/** @param item This parameter can be a combination of the following values:
* @arg @ref LL_DMA_SEC_ITEM_SRC
* LL_DMA_SEC_ITEM_DEST
* @arg @ref LL_DMA_SEC_ITEM_ALL
*/
void LL_DMA_SetChannelSecAttr(DMA_ChannelTypeDef *dma, uint32_t item, uint32_t sec_attr)
/** @param item This parameter can be one of the following values:
* @arg @ref LL_DMA_SEC_ITEM_SRC
* @arg LL_DMA_SEC_ITEM_DEST
*/
uint32_t LL_DMA_GetChannelSecAttr(DMA_ChannelTypeDef *dma, uint32_t item)
Notes: in this LL DMA example, the attributes APIs use:
• The DMA attributes APIs use existing instance of type “DMA_TypeDef“, these
APIs Set and get the security attribute for the given channel(s)
• The IsLocked API return the numerical values “0” or “1”.
• There are two additional functions “LL_DMA_SetChannelSecAttr/
LL_DMA_GetChannelSecAttr” use existing channel instance of type
“DMA_ChannelTypeDef“ and allowing to Set/get the channel xfer security
attribute for the items LL_DMA_SEC_ITEM_SRC (the xfer source) and
LL_DMA_SEC_ITEM_DEST (the xfer destination)
13.2.2.1.2. HAL RIF-aware/TZ-aware peripherals APIs
hal_status_t HAL_{PPP}_{SUBBLOCK}_Set{AttrName}Attr(
{hal_{ppp}_t instance},
{uint32_t Items/subinstances},
hal_{ppp}_{attrname}_attr_t {attrname}_attr);
hal_{ppp}_{attrname}_attr_t HAL_{PPP}_{SUBBLOCK}_Get{AttrName}Attr(
{hal_{ppp}_t instance},
{uint32_t Item/subinstance}
)
hal_status_t HAL_{PPP}_{SUBBLOCK}_Lock{AttrName}Attr(
217

{hal_{ppp}_t instance},
{uint32_t Items/subinstances }
);
hal_{ppp}_attr_lock_status_t HAL_{PPP}_{SUBBLOCK}_IsLocked{AttrName}Attr(
{hal_{ppp}_t instance},
{uint32_t Item/subinstance }
);
// when the PPP HW allows to unlock the attributes
hal_status_t HAL_{PPP}_{SUBBLOCK}_UnLock{AttrName}Attr(
{hal_{ppp}_t instance},
{uint32_t Items/subinstances }
);
With:
• The {PPP} is the HAL module name.
• The {SUBBLOCK} (when existing) within a TZ-aware/RIF-aware HAL module,
it must be applied within set/get attributes APIs.
• The {AttrName} is the attribute abbreviation described here:
• Sec, Priv, Public
• instance is:
• The HAL instance of type hal_ppp_t when existing in the given driver (eg:
hal_gpio_t or hal_flash_t)
• Omitted when the given HAL driver doesn’t use instance like the HAL RCC or
PWR
•
Items/subinstances:
• Use subinstances when the attribute applies to sub-instances meaning multiple
identical resources of the same peripherals (e.g. , pins in case of the GPIO). In
this case these APIs reuse the already existing instances naming and definitions
(e.g. in case of gpio, subinstances = pins and must be set to the defines
HAL_GPIO_PIN_n)
• Use items when the attribute applies to heterogeneous/specific parts of the
given peripheral instance (e.g the RCC oscillators and PLLs and other items).
In this case a set of dedicated defines is provided to list these items with the
following naming rules HAL_{PPP}_{ATTRNAME}_ITEM_{ITEM}
HAL_{PPP}_{ATTRNAME}_ITEM_ALL being required)
• Omitted when the attributes apply to the given PPP instance. In this case only
the hal_ppp_t instance is used (e.g the HAL EXTI where the attributes setting
or lock applies to the EXTI lines represented by the hal_exti_line_t HAL
instance enumeration)
Notes:
• Set attributes APIs can be applied for one or several items/ subinstances (defines Can
be ored/combined when possible).
• Get attributes APIs must be applied for one single item/ subinstance (Cannot be
ored/combined).
218

• Lock/Unlock/IsLocked APIs parameters (instance , items/subinstances) must be
aligned with the given device capability (whether the lock can be performed by the
instance granularity or by item/sub-instance granularity)
• The unlock function must be provided only if it is possible to unlock “on the fly” (i.e
without the need of system reset)
Examples:
RCC:
/* Sec Items list */
#define HAL_RCC_SEC_ITEM_HSE LL_RCC_SEC_ITEM_HSE
#define HAL_RCC_SEC_ITEM_LSI LL_RCC_SEC_ITEM_LSI
...
#define HAL_RCC_SEC_ITEM_SYSCLK LL_RCC_SEC_ITEM_SYSCLK
...
#define HAL_RCC_SEC_ITEM_ALL LL_RCC_SEC_ITEM_ALL
/* Priv Items list */
#define HAL_RCC_PRIV_ITEM_HSE LL_RCC_PRIV_ITEM_HSE
#define HAL_RCC_PRIV_ITEM_LSI LL_RCC_PRIV_ITEM_LSI
...
#define HAL_RCC_PRIV_ITEM_PLL1 LL_RCC_PRIV_ITEM_PLL1
#define HAL_RCC_SEC_ITEM_SYSCLK LL_RCC_PRIV_ITEM_SYSCLK
...
#define HAL_RCC_PRIV_ITEM_ALL LL_RCC_PRIV_ITEM_ALL
/* Public Items list */
#define HAL_RCC_PUBLIC_ITEM_HSE LL_RCC_PUBLIC_ITEM_HSE
#define HAL_RCC_PUBLIC _ITEM_LSI LL_RCC_PUBLIC_ITEM_LSI
...
#define HAL_RCC_PUBLIC_ITEM_SYSCLK LL_RCC_PUBLIC_ITEM_SYSCLK
...
#define HAL_RCC_PUBLIC_ITEM_ALL LL_RCC_PUBLIC_ITEM_ALL
typedef enum
{
HAL_RCC_NSEC = LL_RCC_ATTR_NSEC, /*!< Non-secure access level attribute */
HAL_RCC_SEC = LL_RCC_ATTR_SEC /*!< Secure access level attribute */
} hal_rcc_sec_attr_t;
typedef enum
{
HAL_RCC_NPRIV = LL_RCC_ATTR_NPRIV, /*!< Non-privileged access level attribute */
HAL_RCC_PRIV = LL_RCC_ATTR_PRIV /*!< Privileged access level attribute */
} hal_rcc_priv_attr_t;
219

typedef enum
{
HAL_RCC_ATTR_UNLOCKED = 0U,
HAL_RCC_ATTR_LOCKED = 1U
} hal_rcc_attr_lock_status_t;
hal_status_t HAL_RCC_SetSecAttr(uint32_t items, hal_rcc_sec_attr_t sec_attr);
hal_rcc_sec_attr_t HAL_RCC_GetSecAttr(uint32_t item);
hal_status_t HAL_RCC_SetPrivAttr(uint32_t items, hal_rcc_priv_attr_t priv_attr);
hal_rcc_priv_attr_t HAL_RCC_GetPrivAttr(uint32_t item);
hal_status_t HAL_RCC_SetPublicAttr(uint32_t items, hal_rcc_public_attr_t public_attr);
hal_rcc_public_attr_t HAL_RCC_GetPublicAttr(uint32_t item);
hal_status_t HAL_RCC_LockAttr(uint32_t item);
hal_rcc_attr_lock_status_t HAL_RCC_IsLockedAttr(uint32_t item);
Notes: in this HAL RCC example:
• The instance is omitted as it is not used in the HAL RCC driver
• Use items as the attributes setting applies to heterogenous parts (not identical) of the
RCC like the HSE, LSE, PLL1, SYSCLK
• The lock is possible by item in the above example.
• No unlock API is provided as the unlock is not possible (unlock is done by system
reset)
GPIO:
/* same Pin definitions used overall the HAL GPIO driver */
#define HAL_GPIO_PIN_0 LL_GPIO_PIN_0 /*!< GPIO pin 0 */
#define HAL_GPIO_PIN_1 LL_GPIO_PIN_1 /*!< GPIO pin 1 */
#define HAL_GPIO_PIN_2 LL_GPIO_PIN_2 /*!< GPIO pin 2 */
..
#define HAL_GPIO_PIN_ALL LL_GPIO_PIN_ALL /*!< GPIO pin all*/
typedef enum
{
HAL_GPIO_ATTR_NSEC = LL_GPIO_ATTR_NSEC, /*!< I/O pin is nonsecure */
HAL_GPIO_ATTR_SEC = LL_GPIO_ATTR_SEC /*!< I/O pin is secure */
} hal_gpio_sec_attr_t;
typedef enum
{
HAL_GPIO_ATTR_NPRIV = LL_GPIO_ATTR_NPRIV, /*!< I/O pin is unprivileged */
220

HAL_GPIO_ATTR_PRIV = LL_GPIO_ATTR_PRIV /*!< I/O pin is privileged */
} hal_gpio_priv_attr_t;
typedef enum
{
HAL_GPIO_ATTR_UNLOCKED = 0U, /*!< I/O pin attribues is unlocked */
HAL_GPIO_ATTR_LOCKED = 1U /*!< I/O pin attribues is locked */
} hal_gpio_attr_lock_status_t;
void HAL_GPIO_SetSecAttr(hal_gpio_t gpiox, uint32_t pins, hal_gpio_sec_attr_t sec_attr);
hal_gpio_sec_attr_t HAL_GPIO_GetSecAttr(hal_gpio_t gpiox, uint32_t pin);
void HAL_GPIO_SetPrivAttr(hal_gpio_t gpiox, uint32_t pins, hal_gpio_priv_attr_t priv_attr);
hal_gpio_priv_attr_t HAL_GPIO_GetPrivAttr(hal_gpio_t gpiox, uint32_t pin);
hal_status_t HAL_GPIO_LockAttr(hal_gpio_t gpiox, uint32_t pins);
hal_gpio_attr_lock_status_t HAL_GPIO_IsLockedAttr(hal_gpio_t gpiox, uint32_t pin);
Notes: in this HAL GPIO example the attributes APIs use:
• The hal_gpio_t instance: the port.
• The subinstances are the pins and using the same defines HAL_GPIO_PIN_n as the
overall driver
• The attributes lock can be done by pin(s) in the above example.
EXTI:
typedef enum
{
HAL_EXTI_NSEC = LL_EXTI_ATTR_NSEC,
HAL_EXTI_SEC = LL_EXTI_ATTR_SEC
} hal_exti_sec_attr_t;
typedef enum {
HAL_EXTI_NPRIV = LL_EXTI_ATTR_NPRIV,
HAL_EXTI_PRIV = LL_EXTI_ATTR_PRIV
} hal_exti_priv_attr_t;
typedef enum
{
HAL_EXTI_ATTR_UNLOCKED = 0U, /*!< EXTI attribues are unlocked */
HAL_EXTI_ATTR_LOCKED = 1U /*!< EXTI pin attribues are locked */
} hal_exti_attr_lock_status_t;
hal_status_t HAL_EXTI_SetSecAttr(hal_exit_line_t exit_line, hal_exti_sec_attr_t sec_attr);
hal_exti_sec_attr_t HAL_EXTI_GetSecAttr(hal_exit_line_t exit_line);
221

hal_status_t HAL_EXTI_SetPrivAttr(hal_exit_line_t exit_line, hal_exti_priv_attr_t
priv_attr);
hal_exti_priv_attr_t HAL_EXTI_GetPrivAttr(hal_exit_line_t exit_line);
hal_status_t HAL_EXTI_LockAttr(void);
hal_exti_attr_lock_status_t HAL_EXTI_IsLockedAttr(void);
Notes: in this example, the HAL EXTI attributes APIs use:
• The existing instance enumeration hal_exti_line_t as the attributes applies by line
• There are no subinstance parameter
• The lock/IsLocked functions are void in the above example as the given HW EXTI
peripheral allows to lock all the lines attributes together (not possible to lock
individually the attributes of a given line)
o In case a product allows to lock the attributes by line, then the parameter
hal_exti_line_t must be used.
NVM:
/* NVM security configuration items */
#define HAL_NVM_ITF_SEC_ITEM_PM LL_NVM_SEC_ITEM_PM
..
#define HAL_NVM_ITF_SEC_ITEM_ALL LL_NVM_SEC_ITEM_ALL
/* NVM privilege configuration items */
#define HAL_NVM_ITF_PRIV_ITEM_SYS LL_NVM_PRIV_ITEM_SYS
..
#define HAL_NVM_ITF_PRIV_ITEM_ALL LL_NVM_PRIV_ITEM_ALL
/* NVM lock configuration items */
#define HAL_NVM_ITF_LOCK_ITEM_PM LL_NVM_LOCK_ITEM_PM
..
#define HAL_NVM_ITF_LOCK_ITEM_ALL LL_NVM_LOCK_ITEM_ALL
typedef enum
{
HAL_NVM_ITF_NSEC = LL_NVM_ATTR_NSEC,
HAL_NVM_ITF_SEC = LL_NVM_ATTR_SEC
} hal_nvm_itf_sec_attr_t;
/*! HAL NVM ITF Privilege attribute enumeration definition */
typedef enum
{
HAL_NVM_ITF_NPRIV = LL_NVM_ATTR_NPRIV,
HAL_NVM_ITF_PRIV = LL_NVM_ATTR_PRIV
} hal_nvm_itf_priv_attr_t;
/*! HAL NVM ITF Lock attribute enumeration definition */
typedef enum
{
HAL_NVM_ITF_ATTR_UNLOCKED = 0U,
HAL_NVM_ITF_ATTR_LOCKED = 1U
} hal_nvm_itf_attr_lock_status_t;
hal_status_t HAL_NVM_ITF_SetSecAttr(hal_nvm_t instance,
uint32_t item,
222

hal_nvm_itf_sec_attr_t sec_attr);
hal_nvm_itf_sec_attr_t HAL_NVM_ITF_GetSecAttr(hal_nvm_t instance,
uint32_t item);
hal_status_t HAL_NVM_ITF_SetPrivAttr(hal_nvm_t instance,
uint32_t item,
hal_nvm_itf_priv_attr_t priv_attr);
hal_nvm_itf_priv_attr_t HAL_NVM_ITF_GetPrivAttr(hal_nvm_t instance, uint32_t item);
hal_status_t HAL_NVM_ITF_LockAttr(hal_nvm_t instance,
uint32_t item);
hal_nvm_itf_attr_lock_status_t HAL_NVM_ITF_IsLockedAttr(hal_nvm_t instance,
uint32_t item);
Notes: in this HAL NVM example, the attributes APIs use:
• The existing instance enumeration hal_nvm_t
• items as the attributes setting applies to heterogenous parts (not identical) of the
NVM
• The lock/IsLocked functions use the instance enumeration hal_nvm_t attributes
and items as second parameters as the attributes lock is possible by item.
DMA:
typedef enum
{
HAL_DMA_NSEC = LL_DMA_ATTR_NSEC,
HAL_DMA_SEC = LL_DMA_ATTR_SEC
} hal_dma_sec_attr_t;
typedef enum {
HAL_DMA_NPRIV = LL_DMA_ATTR_NPRIV,
HAL_DMA_PRIV = LL_DMA_ATTR_PRIV
} hal_dma_priv_attr_t;
hal_status_t HAL_DMA_SetSecAttr(hal_dma_channel_t instance,
hal_dma_sec_attr_t sec_attr);
hal_dma_sec_attr_t HAL_DMA_GetSecAttr(hal_dma_channel_t instance);
hal_status_t HAL_DMA_SetPrivAttr(hal_dma_channel_t instance,
hal_dma_priv_attr_t priv_attr);
hal_dma_priv_attr_t HAL_DMA_GetPrivAttr(hal_dma_channel_t instance);
#define HAL_DMA_SEC_ITEM_SRC LL_DMA_SEC_ITEM_SRC
#define HAL_DMA_SEC_ITEM_DEST LL_DMA_SEC_ITEM_DEST
#define HAL_DMA_SEC_ITEM_ALL LL_DMA_SEC_ITEM_ALL
hal_status_t HAL_DMA_SetXferSecAttr(hal_dma_channel_t instance,
uint32_t items,
hal_dma_sec_attr_t sec_attr);
hal_dma_sec_attr_t HAL_DMA_GetXferSecAttr(hal_dma_channel_t instance, uint32_t item);
Notes: In HAL DMA there are two level of attribute setting:
• Channel attribute setting: meaning setting the DMA channel to be used by a secure or
non-secure privilege or non-privilege context.
223

o This is handled by the functions HAL_DMA_SetSecAttr/
HAL_DMA_GetSecAttr and HAL_DMA_SetPrivAttr/
HAL_DMA_GetPrivAttr.
o These functions use the HAL DMA existing instance hal_dma_channel_t. it
does not use neither items nor sub-instances.
• Transfer attribute setting: meaning setting the source/destination of the given channel
transfer to be from/to a secure or a non-secure area.
o This is handled by the functions HAL_DMA_SetXferSecAttr/
HAL_DMA_GetXferSecAttr.
o These functions use the HAL DMA existing instance hal_dma_channel_t plus
an “item(s)” parameter that could be the source or the destination of the
transfer.
13.2.3. Security compile-time conditional checks
In the stm32tnxx.h CMSIS DFP file, two defines must be provided allowing to identify the
current execution context secure or non-secure as follow:
//stm32tnxx.h
...
/* Cortex-M Security Extension: secure compilation */
#if defined (__ARM_FEATURE_CMSE) && (__ARM_FEATURE_CMSE == 3U)
#define CMSE_SECURE_EXECUTION_ENVIRONMENT
#endif /* __ARM_FEATURE_CMSE */
/* Cortex-M Security Extension: non-secure compilation */
#if defined (__ARM_FEATURE_CMSE) && (__ARM_FEATURE_CMSE == 1U)
#define CMSE_NONSECURE_EXECUTION_ENVIRONMENT
#endif /* __ARM_FEATURE_CMSE */
These defines must be used within the HAL and LL implementation as a conditional
compilation switch when there is a need to differentiate between the secure and non-secure
execution context.
• Case of the resource/register is banked between the secure and non-secure context
In this case, the corresponding registers are duplicated for secure and non-secure
context.
The LL and HAL drivers must provide:
o A context agnostic API performing the action for the current context as follow:
__STATIC_INLINE return type LL_PPP_{SUB-BLOCK}_XXXXXXXXX(param1, param2 …)
{
#if defined (CMSE_SECURE_EXECUTION_ENVIRONMENT)
STM32_SET_BIT(PPPx->secure_reg, XXXXXXXXXXXXX);
224

#else
STM32_SET_BIT(PPPx->nsecure_reg, XXXXXXXXXXXXX);
#endif /* CMSE_SECURE_EXECUTION_ENVIRONMENT */
}
return type HAL_PPP_{SUB-BLOCK}_XXXXXXXX(param1, param2 …)
{
...
LL_PPP_{SUB-BLOCK}_XXXXXXXXX(param1, param2 …)
...
}
o A cross “NS” API allowing the secure context to perform the action on the non-
secure side. This APIs is available for secure context only and thus delimited
by the compilation define CMSE_SECURE_EXECUTION_ENVIRONMENT:
#if defined (CMSE_SECURE_EXECUTION_ENVIRONMENT)
__STATIC_INLINE return type LL_PPP_{SUB-BLOCK}NS_XXXXXXXXX(param1, param2 …)
{
STM32_SET_BIT(PPPx_NS->nsecure_reg, XXXXXXXXXXXXX);
}
#endif /* CMSE_SECURE_EXECUTION_ENVIRONMENT */
#if defined (CMSE_SECURE_EXECUTION_ENVIRONMENT)
return type HAL_PPP_{SUB-BLOCK}NS_XXXXXXXX(param1, param2 …)
{
...
LL_PPP_{SUB-BLOCK}NS_XXXXXXXXX(param1, param2 …)
...
}
#endif /* CMSE_SECURE_EXECUTION_ENVIRONMENT */
• Case of the resource/register is applicable/provided for the secure context only
In this case, the corresponding HAL and LL APIs are fully delimited by the
compilation define CMSE_SECURE_EXECUTION_ENVIRONMENT.
#if defined (CMSE_SECURE_EXECUTION_ENVIRONMENT)
__STATIC_INLINE return type LL_PPP_{SUB-BLOCK}_XXXXXXXX(param1, param2 …)
{
MODIFY_REG(PPPx->reg, XXXXXX, xxxxx);
}
#endif /* CMSE_SECURE_EXECUTION_ENVIRONMENT */
#if defined (CMSE_SECURE_EXECUTION_ENVIRONMENT)
return type HAL_PPP_{SUB-BLOCK}_XXXXXXXX(param1, param2 …)
225

{
...
LL_PPP_{SUB-BLOCK}_XXXXXXXX(param1, param2 …)
...
}
#endif /* CMSE_SECURE_EXECUTION_ENVIRONMENT */
• Case of the resource/register is applicable/provided for the non-secure context
only
In this case, the corresponding HAL and LL APIs are fully delimited by the
compilation define CMSE_NONSECURE_EXECUTION_ENVIRONMENT.
#if defined (CMSE_NONSECURE_EXECUTION_ENVIRONMENT)
__STATIC_INLINE return type LL_PPP_{SUB-BLOCK}_XXXXXXXX(param1, param2 …)
{
MODIFY_REG(PPPx->reg, XXXXXX, XXXXXX);
}
#endif /* CMSE_NONSECURE_EXECUTION_ENVIRONMENT */
#if defined (CMSE_NONSECURE_EXECUTION_ENVIRONMENT)
return type HAL_PPP_{SUB-BLOCK}_XXXXXXXX(param1, param2 …)
{
...
LL_PPP_{SUB-BLOCK}_XXXXXXXX(param1, param2 …)
...
}
#endif /* CMSE_NONSECURE_EXECUTION_ENVIRONMENT */
13.2.4. Privilege compile-time conditional checks
In the stm32tnxx.h CMSIS DFP file, a macro must be provided allowing to identify the
current execution context privilege or not as follow:
#define STM32_IS_PRIVILEGED_EXECUTION() ((__get_CONTROL() & CONTROL_nPRIV_Mask) == 0U)
Within the HAL implementation, a check must be done to check if the current privilege state
allows the given action and return HAL_ERROR if not.
Example
hal_status_t HAL_RCC_SetPrivAttr(hal_rcc_priv_attr_t priv_attr)
{
if (STM32_IS_PRIVILEGED_EXECUTION() == 0U)
{
return HAL_ERROR;
}
LL_RCC_SetPrivAttr((uint32_t)priv_attr);
226

return HAL_OK;
}
227

14. HAL Versioning and dependencies files

The dependencies file is a markdown file that must contain a table showing the different HAL
drivers, their respective versions and different other components they depend on. The
dependencies table must be generated, during the HAL packaging, by an internal script that
parse the HAL PDSC file and generates the dependencies.md file.
The dependencies table must be formatted as follows:
| Driver      |          | dependencies  |          |
| ----------- | -------- | ------------- | -------- |
| HAL Driver  | version  | Component     | version  |

|     |     | HAL comp B (E.g. RCC)  |  x.y.z  |
| --- | --- | ---------------------- | ------- |

|     | x.y.z  |                        |        |
| --- | ------ | ---------------------- | ------ |
|     |        | HAL comp C (E.g. DMA)  | x.y.z  |
HAL comp A
x.y.z
|     |     | HAL comp D  |     |
| --- | --- | ----------- | --- |

|     |     | DFP  | x.y.z  |
| --- | --- | ---- | ------ |

|     |     | FreeRTOS  | x.y.z  |
| --- | --- | --------- | ------ |

x.y.z
CMSIS Core
|              |        | HAL comp B (E.g. RCC)  | x.y.z  |
| ------------ | ------ | ---------------------- | ------ |
| HAL comp B   | x.y.z  |                        |        |
|              |        | HAL comp C (E.g. DMA)  | x.y.z  |

|     |     | HAL comp F  | x.y.z  |
| --- | --- | ----------- | ------ |

|     |     | DFP  | x.y.z  |
| --- | --- | ---- | ------ |

|     |     | CMSIS Core  | x.y.z  |
| --- | --- | ----------- | ------ |

Note: The complete tree of dependencies must be displayed in the dependencies column. For
example, if a HAL PPP has dependencies on another peripheral driver, that driver and all its
dependencies must be fully listed.

IMPORTANT NOTICE – PLEASE READ CAREFULLY
STMicroelectronics International NV and its affiliates (“ST”) reserve the right to make changes corrections, enhancements, modifications, and improvements to
ST products and/or to this document any time without notice.
This document is provided solely for the purpose of obtaining general information relating to an ST product. Accordingly, you hereby agree to make use of this
document solely for the purpose of obtaining general information relating to the ST product. You further acknowledge and agree that this document may not be
used in or in connection with any legal or administrative proceeding in any court, arbitration, agency, commission or other tribunal or in connection with any
action, cause of action, litigation, claim, allegation, demand or dispute of any kind. You further acknowledge and agree that this document must not be construed
as an admission, acknowledgement or evidence of any kind, including, without limitation, as to the liability, fault or responsibility whatsoever of ST or any of its
affiliates, or as to the accuracy or validity of the information contained herein, or concerning any alleged product issue, failure, or defect. ST does not promise that
this document is accuratfe or error free and specifically disclaims all warranties, express or implied, as to the accuracy of the information contained herein.
Accordingly, you agree that in no event will ST or its affiliates be liable to you for any direct, indirect, consequential, exemplary, incidental, punitive, or other
damages, including lost profits, arising from or relating to your reliance upon or use of this document.
Disclosure of this document to any non-authorized party must be previously authorized by ST only under the provision of a proper confidentiality contractual
arrangement executed between ST and you and must be treat as strictly confidential.
At all times you will comply with the following securities rules:
•  Do not copy or reproduce all or part of this document.
•  Keep this document locked away.
•  Further copies can be provided on a “need to know basis”. Please contact your local ST Sales Office or document writer.
Purchasers should obtain the latest relevant information on ST products before placing orders. ST products are sold pursuant to ST’s terms and conditions of sale
in place at the time of order acknowledgment, including, without limitation, the warranty provisions thereunder.
In that respect please note that ST products are not designed for use in some specific applications or environments described in above mentioned terms and
conditions.
228

Purchasers are solely responsible for the choice, selection, and use of ST products and ST assumes no liability for application assistance or the design of
purchasers’ products.
Information furnished is believed to be accurate and reliable. However, ST assumes no responsibility for the consequences of use of such information nor for any
infringement of patents or other rights of third parties which may result from its use. No license, express or implied, to any intellectual property right is granted by
ST herein.
Resale of ST products with provisions different from the information set forth herein must void any warranty granted by ST for such product.
ST and the ST logo are trademarks of ST. For additional information about ST trademarks, please refer to www.st.com/trademarks. All other product or service
names are the property of their respective owners.
Information in this document supersedes and replaces information previously supplied in any prior versions of this document.
© 2025 STMicroelectronics – All rights reserved
229

Annexes
Annexe 1: Abbreviation table
The following tables provides terms abbreviations that might be used in case we need shorted
an API naming due to coding rules or / and MISR-C rules
Term Abbreviation
absolute abs
accept accept
accessed accessed
acknowledge ack
action act
active active
add add
address addr
adjust adj
alarm alm
alarming alarming
allocate alloc
application app
argument arg
assign assign
assignment assign
attributes attr
automatic auto
auxiliary aux
available avail
average avg
background bgnd
balance bal
bank bank
base base
big big
binary bin
bit bit
block blk
bound bound
230

Term Abbreviation
break brk
broadcast broadcast
buffer buf
cache cache
calculate calc
calculation calc
calibration cal
change chng
Callback cb
channel ch
character char
charge chrg
check chk
class class
clear clr
client client
clock clk
clone clone
close close
cluster clus
code code
coefficient coeff
column col
command cmd
communications comm
compare cmp
complement cpl
computation comp
compute comp
condition cond
configuration cfg
configure cfg
conflict conflict
congestion cong
connection conn
consecutive consec
231

Term Abbreviation
constant const
continuous contin
control ctrl
controller ctrlr
convention conv
conversion conv
copy copy
count cnt
counter ctr
create create
creation create
current cur
data data
datagram datagram
date date
day day
deallocate dealloc
decrement dec
default dflt
defined def
definition def
degree deg
delay dly
delete del
denominator denom
depth depth
descriptor desc
destination dest
detect detect
development dev
device dev
digit dig
digital dig
disable dis
disabled dis
discard discard
232

Term Abbreviation
discharge disc
disk disk
done done
down down
driver drv
dummy dummy
duplicate dup
duration dur
dynamic dyn
echo echo
edge edge
efficiency eff
elapsed elapsed
enable en
enabled en
endian endian
endpoint ep
enter enter
entry entry
erase erase
error err
Ethernet ether
event event
exceed exceed
exception except
exchange xchng
exit exit
extension ext
extern ext
external ext
interrupt it
interrupt service routine isr
invalid invalid
isolate isolated
isolated isolated
journal journal
233

Term Abbreviation
journaling journal
jump jump
key key
keyboard kbd
kernel Ker
lamp lamp
last last
latch latch
left left
length len
level level
limit lim
linear lin
list list
listen listen
load load
local local
location loc
lock lock
logical logical
loose loose
lost lost
low lo
mail box mbox
management mgmt
manager mgr
manual man
map map
mask msk
master master
maximum max
measurement meas
memory mem
message msg
milliseconds ms
minimal min
234

Term Abbreviation
minimum min
minute min
mode mode
module module
monitor mon
more more
mount mount
multiplier mult
negative neg
network net
next next
nominal nom
number nbr
numerator numer
object obj
octet octet
operation oper
option opt
optional opt
order order
origin org
output out
overflow ovf
over ovr
packet pkt
page page
parameter param
partition partition
pattern pattern
peek peek
pend pend
percentage pct
peripheral periph
phase phase
point pt
polarity pol
235

Term Abbreviation
pool pool
position pos
post post
power pwr
pre pre
previous prev
primary prim
priority prio
problem prob
procedure proc
process process
product prod
program program
protocol protocol
protect prot
provide pub
pulse width modulation pwm
queue q
quick quick
random random
ratio ratio
ready rdy
recall rcl
receive rx
receiver rx
record rec
recover rec
reduce red
reference ref
register reg
relative rel
remain rem
remainder rem
remove remove
repeat rep
reply reply
236

Term Abbreviation
report report
request req
reset reset
resource rsrc
response resp
restart restart
result res
resume resume
return rtn
right right
route route
row row
run run
sample samp
scale scale
scaling scaling
schedule sched
scheduler sched
search srch
secondary sec
segment seg
select sel
send send
sender sender
sense sense
separate sep
sequence seq
server server
service serv
session sess
set set
setpoint stp
shift shift
shutdown sd
signal signal
size size
237

Term Abbreviation
small small
software soft
source src
spare spare
speed spd
start start
state state
state machine sm
stop stop
storage sto
stream stream
strict strict
string str
structure struct
subroutine sub
suspend suspend
symbol symbol
synchronize sync
system sys
table tbl
task task
target tgt
test test
text text
time time
time base tbl
time stamp ts
time to live ttl
timer tmr
timing timing
token token
total tot
transmit tx
transmitted txd
trigger trig
truncate trunc
238

Term Abbreviation
type type
undefined undf
unknown unknown
unlink unlink
unlock unlock
unused unused
update update
upload upload
user user
utility utility
valid valid
value val
verified verifd
verify verify
version ver
volume vol
wait wait
wide wide
write wr
239