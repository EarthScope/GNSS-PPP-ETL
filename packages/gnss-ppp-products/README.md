# gnss-ppp-products: Your Cuppa Tea for Precise Point Positioning (PPP) Resources

## Navigating the Bloody Minefield of GNSS Data for PPP

Right, listen up, you lot. If you're knee-deep in Precise Point Positioning (PPP) – and let's face it, who isn't these days? – you'll know that quality GNSS products are absolutely paramount. The International GNSS Service (IGS), bless 'em, is the grand old dame providing us with the precise orbit and clock products, among other bits and bobs, that let us get down to centimetre-level accuracy. But let's be honest, trying to find your way through the IGS's vast archives, with all their Ultra-Rapid, Rapid, and Final products (IGU, IGR, IGS), each with their own latency and accuracy quirks, can be an absolute dog's dinner. This `gnss-ppp-products` package? It's here to sort out that mess, acting as your trusty ETL (Extract, Transform, Load) engine, specifically designed to wrangle these essential GNSS resources. No fuss, no bother.

## The Gist: What's This Contraption For, Then?

This package is essentially the chap in charge of getting, setting up, and querying all your GNSS products. Its main job is to clear away all the confusing rubbish from different data sources and those daft file naming conventions. That way, you boffins and code-slingers can actually focus on the geodetic bits, instead of tearing your hair out over data logistics.

### What It Does, Innit:

*   **Proper Clever Configuration**: At its heart, this kit uses `Pydantic` models to take your perfectly sensible YAML config files (like `igs_config.yaml`) and turn 'em into something dynamic and useful. These YAMLs don't just list who's providing the data; they detail all the fiddly bits of the products too – quality, sampling rates, available stations, the whole nine yards.
*   **A Search Engine That Actually Works**: Instead of you fumbling around in dusty FTP/HTTP directories, this package builds a cracking query system. You give it a few high-level parameters – product `format`, `content`, `time`, and maybe `center`, `campaign`, `quality`, `interval`, `duration` if you're feeling fancy – and it'll smartly figure out the exact file patterns to find what you're after on remote servers. It can even use a bit of regex magic if you leave out some optional bits, making it feel like a proper API for sniffing out GNSS data.
*   **Your Own Local Stash**: Once you've found and grabbed your products, they can be neatly tucked away in a local data sink. Handy for keeping things consistent and tracked for all your subsequent analyses.
*   **ETL Orchestration**: The package integrates with orchestration tools like `Dagster` to build resilient and repeatable pipelines for fetching and preparing GNSS products, ensuring data freshness and integrity.

## The IGS Angle: Keeping PPP Shipshape

Our ability to do high-precision PPP is utterly dependent on the quality and sheer availability of IGS products. This package has been built from the ground up to understand the ins and outs of IGS (and other) analysis centres. So whether you're after the crystal-ball predictions of Ultra-Rapid orbits for a spot of real-time caper, or the dead-on accuracy of Final products for post-processing marathon, this system gives you the means to ask for 'em, find 'em, and get 'em. It's essentially the bridge between IGS's valuable data and our project's computational needs. Marvellous.



## Current Center Product Offerings

For your convenience, here's a rundown of the products each analysis center currently provides, according to our configurations. No need to go digging through endless directories, eh?

### CDDIS (NASA CDDIS)

- `cddis_clock`
- `cddis_gim`
- `cddis_leap_seconds`
- `cddis_nav`
- `cddis_orbit`

### COD (Center for Orbit Determination in Europe (AIUB))

- `code_bias`
- `code_clock`
- `code_erp`
- `code_gim`
- `code_orbit`

### ESA (ESA/ESOC)

- `esa_clock`
- `esa_gim`
- `esa_orbit`

### GFZ (GFZ Potsdam)

- `gfz_clock`
- `gfz_orbit`

### IGS (International GNSS Service (via IGN France))

- `igs_atx`
- `igs_atx_archive`
- `igs_bias`
- `igs_clock`
- `igs_erp`
- `igs_nav`
- `igs_obx`
- `igs_orbit`

### VMF (TU Wien (Vienna))

- `vmf_orography_1x1`
- `vmf_orography_5x5`
- `vmf_vmf1`
- `vmf_vmf3_1x1`
- `vmf_vmf3_5x5`

### WUM (Wuhan University GNSS Research Center)

- `wuhan_bias`
- `wuhan_bias_weekly`
- `wuhan_clock`
- `wuhan_clock_weekly`
- `wuhan_erp`
- `wuhan_erp_weekly`
- `wuhan_gim`
- `wuhan_leap_seconds`
- `wuhan_nav`
- `wuhan_obx`
- `wuhan_obx_weekly`
- `wuhan_orbit`
- `wuhan_orbit_weekly`
- `wuhan_sat_parameters`


## Under the Bonnet: How It Works

The whole shebang is designed around tidy data and keeping things separate, like a well-organised shed:

1.  **YAML Blueprints**: All the initial product specifications (e.g., `IGS0OPSFIN_YYYYDDD0000_01D_05M_ORB.SP3.*`) are written down in good old YAML files.
2.  **Pydantic Brings 'Em to Life**: These YAMLs are then slurped up by `Pydantic` `ProductConfig` and `RinexConfig` models. They don't just check everything's in order, but they also expand all those attribute sets (like `quality_set`, `station_set`) into every conceivable combination.
3.  **Dynamic Query Objects**: For a specific date, the system spits out a flat list of `ProductFileQuery` or `RinexFileQuery` objects. Each one is a unique, fully resolved potential file on a remote server, with its exact path and filename pattern. This clever combinatorial approach means you won't miss a trick when searching for all the variations of a product.

## Getting Stuck In (The Theory, Anyway)

If you're looking to use this package, you'd typically:
1.  Pick or define the right analysis centre configuration (`src/gnss_ppp_products/resources/config/centers/*.yaml`).
2.  Get your `GNSSCenterConfig` object sorted.
3.  Call methods like `build_product_queries(date=...)` to generate a list of those handy `ProductFileQuery` objects.
4.  Then, off you go, execute those queries to find and download your desired GNSS products.

So there you have it. This solid framework empowers you, the eager graduate student or researcher, to get a handle on the crucial data needed for your PPP investigations. Leaving you more time for the proper science, and less time for pointless faffing about with file downloads. Good show!