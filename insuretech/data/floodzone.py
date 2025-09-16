import modal

app = modal.App("floodzone")

# Create an image with requests installed
image = modal.Image.debian_slim().pip_install("requests")

STFIPS = [
    '01',
    #'02',
]

@app.function(image=image)
def get_floodzone_manifest():
    import requests  # Import only inside the function
    results = []
    for fips in STFIPS:
        url = f"https://msc.fema.gov/portal/advanceSearch?affiliate=fema&query&selstate={fips}&selcounty={fips}001&selcommunity={fips}001C&searchedCid={fips}001C&method=search"
        response = requests.get(url)
        results.append({
            'fips': fips,
            'status_code': response.status_code,
            'content': response.text[:100]
        })
    return results

@app.local_entrypoint()
def main():
    results = get_floodzone_manifest.remote()
    print(results)