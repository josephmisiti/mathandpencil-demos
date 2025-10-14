#!/usr/bin/env python3

import click
import geopandas as gpd


@click.command()
@click.argument('filename', type=click.Path(exists=True))
@click.option('--field', default='ATTRIBUTE', help='Field to get unique values from')
def main(filename, field):
    gdf = gpd.read_file(filename)

    if field not in gdf.columns:
        click.echo(f"Error: Field '{field}' not found in data", err=True)
        click.echo(f"Available fields: {', '.join(gdf.columns)}", err=True)
        return

    unique_values = sorted(gdf[field].unique())

    click.echo(f"\nUnique values in '{field}' ({len(unique_values)} total):\n")
    for value in unique_values:
        click.echo(f"  - {value}")


if __name__ == '__main__':
    main()
