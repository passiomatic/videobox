from setuptools import setup, find_packages

setup(
    name='videobox',
    version='0.1.0',
    description='Video download and playback machine',
    author='Andrea Petrin',
    author_email='andrea@passiomatic.com',
    packages=find_packages(),
    data_files=[('.',['loading.png', 'icon.png'])],
    # https://setuptools.pypa.io/en/latest/userguide/entry_point.html
    entry_points={'console_scripts': ['videobox=videobox.main:run_app']},
    include_package_data=True,
)