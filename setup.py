from distutils.core import setup
setup(
    name = 'loosejson',
    packages = ['loosejson'],
    version = '1.0.3',
    description = '',
    long_description = '',
    author = 'Florian Dietz',
    author_email = 'floriandietz44@gmail.com',
    url = '',
    license = 'MIT',
    package_data={
        '': ['*.txt'],
    },
    install_requires=[
        'six==1.11.0',
    ],
)
