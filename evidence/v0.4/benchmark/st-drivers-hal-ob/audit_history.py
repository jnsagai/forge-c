"""Literal SC-001 history audit, separate from the zero-hand-profile-read check.

The existing legacy GPIO reset-description correction is reported as an exception;
this script must not turn it into a zero-change claim.
"""
import subprocess

from forge_factory.common import REPO_ROOT

base = '11482e3'
paths = ['config/factory/peripherals', *[
    'examples/' + name for name in ('0010e-st-cube-gpio-hal-ob', '0011e-st-cube-spi-hal-ob',
                                  '0012e-st-cube-usart-hal-ob', '0013e-st-cube-tim-hal-ob')]]
history = subprocess.check_output(['git', 'log', '--format=%H %s', '--name-only', base + '..HEAD', '--', *paths],
                                  cwd=REPO_ROOT, text=True)
print(history)
change = subprocess.check_output(['git', 'diff', base, 'HEAD', '--', 'config/factory/peripherals'],
                                 cwd=REPO_ROOT, text=True)
print(change)
assert not change, ('STRICT_SC001_EXCEPTION: unused legacy GPIO target-model reset description was corrected. '
                    'The separate read-trace audit proves onboarding does not read that profile. '
                    'Owner review must adjudicate the literal history criterion; no zero-change claim.')
print('PASS literal SC-001 history criterion')
