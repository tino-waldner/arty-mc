from setuptools import find_packages, setup

setup(
    name="arty-mc",
    version="0.1.4",
    packages=find_packages(),
    install_requires=[
        "textual",
        "requests",
        "dohq-artifactory",
        "pyyaml",
    ],
    author="Tino Waldner",
    author_email="tino.waldner@gmail.com",
    description="Dual-pane terminal file manager for Artifactory",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/tino-waldner/arty-mc",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Utilities",
        "Environment :: Console",
    ],
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "arty-mc=arty_mc.arty_mc:main",
        ],
    },
)
