"""yea setup."""

from setuptools import setup


setup(
    name="yea-wandb",
    version="0.9.3",
    description="Test harness wandb plugin",
    packages=["yea_wandb"],
    install_requires=[
        "Flask",
        "requests",
        "responses",
        "pandas",
        "yea==0.9.0",
        "wandb>=0.13.10.dev1",
        # "wandb @ git+https://github.com/wandb/wandb.git@jhr-relay-split",
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
