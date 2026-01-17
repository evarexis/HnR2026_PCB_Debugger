"""
Setup script for PCB Bring-Up Assistant
"""
from setuptools import setup, find_packages
from pathlib import Path

readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding='utf-8') if readme_file.exists() else ""

setup(
    name="pcb-bringup-assistant",
    version="1.0.0",
    author="YName",  
    author_email="cxiy06@gmail.com, avecado5649@gmail.com", 
    description="Automated PCB bring-up checklist generation from KiCad schematics",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/evarexis/HnR2026_PCB_Debugger",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering :: Electronic Design Automation (EDA)",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "sexpdata>=0.0.3",
        "pydantic>=2.0.0",
        "wxPython>=4.2.0",
        "openai>=2.0.0", 
        "google-generativeai>=0.8.0",  
        "python-dotenv>=1.0.0",  
    ],
    entry_points={
        'console_scripts': [
            'pcb-bringup=bringup_plugin:main', 
        ],
    },
    include_package_data=True,
    zip_safe=False,
)