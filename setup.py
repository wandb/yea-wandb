# -*- coding: utf-8 -*-
"""yea setup."""

from setuptools import setup


setup(
    name='yea-wandb',
    version='0.2.1',
    description="Test harness wandb plugin",
    packages=[
        'yea_wandb'
    ],
    install_requires=[
        'yea==0.2.1',
    ],
    package_dir={'': 'src'},
    entry_points={
        'yea.plugins': [
            'yea_wandb = yea_wandb.plugin',
        ]
    },
    zip_safe=False,
    include_package_data=True,
    license="MIT license",
    python_requires='>=3.5',
)
