# setup.py
"""
Установочный скрипт для парсера
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [
        line.strip() for line in fh if line.strip() and not line.startswith("#")
    ]

setup(
    name="morele-parser",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="Professional parser for morele.net with Ukrainian translation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/morele-parser",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Internet :: WWW/HTTP :: Indexing/Search",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
            "mypy>=0.900",
        ],
        "deepl": ["deepl>=1.15.0"],
        "mysql": ["PyMySQL>=1.0.0"],
    },
    entry_points={
        "console_scripts": [
            "morele-parser=main:main",
            "morele-tools=cli_tools:main",
            "morele-health=monitor_health:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.yaml", "*.yml", "*.json", "*.txt"],
    },
    zip_safe=False,
)
