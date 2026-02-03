from setuptools import setup

setup(
    name="linkfinder",
    version="1.0",
    py_modules=["linkfinder"],
    install_requires=[
        "requests",
        "beautifulsoup4", 
        "ddgs",
        "googlesearch-python"
    ],
    entry_points={
        "console_scripts": [
            "linkfinder=linkfinder:main",
        ],
    },
)
