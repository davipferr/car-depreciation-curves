"""Build-time data pipeline for the car depreciation site.

``fipe`` wraps the Tabela FIPE endpoints, ``catalogo`` turns FIPE's free-text
version names into families and attributes, ``bcb`` fetches the IPCA used to
deflate prices and ``curves`` fits the depreciation rates. The Observable
Framework data loaders in ``src/data`` are thin scripts that call into this
package and write the result to stdout.
"""
