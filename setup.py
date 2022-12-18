"""yea setup."""

from setuptools import setup


setup(
    name="yea-wandb",
    version="0.9.0",
    description="Test harness wandb plugin",
    packages=["yea_wandb"],
    install_requires=[
        "Flask",
        "requests",
        "responses",
        "pandas",
        "yea==0.9.0",
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
