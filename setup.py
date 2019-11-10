from distutils.core import setup
setup(
    name = 'loosejson',
    packages = ['loosejson'],
    version = '1.0.0',
    description = 'A library containing basic code useful when creating Docker Images for elody.com',
    long_description = 'A library containing basic code useful when creating Docker Images for elody.com',
    author = 'Florian Dietz',
    author_email = 'floriandietz44@gmail.com',
    license = 'MIT',
    package_data={
        '': ['*.txt'],
    },
    install_requires=[
        'six==1.11.0',
    ],
)
