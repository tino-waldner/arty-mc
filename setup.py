from setuptools import find_packages, setup  # type: ignore

setup(
    name="arty-mc",
    version="0.1.8",
    packages=find_packages(),
    install_requires=[
        "textual>=0.52.0",
        "requests>=2.28.0",
        "dohq-artifactory>=0.9.2",
        "pyyaml>=6.0",
    ],
    author="Tino Waldner",
    author_email="tino.waldner@gmail.com",
    description="Dual-pane terminal file manager for Artifactory",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/tino-waldner/arty-mc",
    license="MIT",
    classifiers=[
        "Programming Language :: Python :: 3",
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
