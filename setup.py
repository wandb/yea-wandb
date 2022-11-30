"""yea setup."""

from setuptools import setup


setup(
    name="yea-wandb",
    version="0.8.14",
    description="Test harness wandb plugin",
    packages=["yea_wandb"],
    install_requires=[
        "Flask",
        "requests",
        "yea==0.8.6",
    ],
    package_dir={"": "src"},
    entry_points={
        "yea.plugins": [
            "yea_wandb = yea_wandb.plugin",
        ]
    },
    zip_safe=False,
    include_package_data=True,
    license="MIT license",
    python_requires=">=3.6",
)
