from setuptools import setup, find_packages

setup(
    name="gitty-auth",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "fastapi",
        "pyjwt",
        "passlib",
    ],
)
