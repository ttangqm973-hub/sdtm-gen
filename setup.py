from setuptools import setup, find_packages

setup(
    name="sdtm_gen",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "openpyxl>=3.1.0",
        "pydantic>=2.0.0",
        "Jinja2>=3.1.0",
        "click>=8.1.0",
    ],
    entry_points={
        "console_scripts": [
            "sdtm-gen=cli:main",
        ],
    },
    python_requires=">=3.10",
)
