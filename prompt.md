Act as a senior backend engineer and DevOps architect. Build the first working draft of the catalog and orders components for my beverage-store microservices project.

The project’s main purpose is to demonstrate AWS DevOps engineering: Docker, EKS, Helm, Terraform, GitHub Actions and monitoring. Keep the application understandable and practical. Do not turn this into a data engineering platform.

## Business context and inputs

I will provide:
1. `dataset_for_eks.pdf`: an Andhra Pradesh beverage price list dated 15 October 2024.
2. A folder of product images that I will upload to a private S3 bucket.

The PDF contains category headings, supplier codes, brand codes/names, product codes, bottle sizes, size codes and MRP. Some cells wrap across lines, and serial numbering restarts by category.

Treat prices as historical demo data, not verified current prices. Extract the actual records; do not invent missing products, prices, stock or image mappings.

Categories should include `whisky`, `brandy`, `gin`, `rum`, `vodka`, `beer` and `wine`, importing only categories present in the source. Preserve distinctions such as strong/lager beer in an optional subcategory.

## Technology and scope

- Java 17 and Spring Boot for two independently deployable services:
  - `catalog-service`
  - `order-service`
- PostgreSQL, hosted locally through Docker Compose initially and later on Amazon RDS.
- One PostgreSQL instance with two logical databases, `catalog` and `orders`, and separate application users.
- Flyway for database schema migrations.
- Maven.
- Python only for the one-time PDF extraction and seed preparation, if needed.
- No Kafka, Spark, Airflow, Elasticsearch or unnecessary frameworks.
- No frontend, AWS provisioning or actual EKS deployment in this first draft.

Inspect the workspace before creating files. Preserve existing work and never embed credentials.

## 1. Catalog database

Use one practical `catalog_items` table for the first version, with one sellable item per source product code.

Include:
- Internal UUID identifier
- Unique `product_code`
- `supplier_code`
- `brand_code`
- `product_name`
- `category`
- Optional `subcategory`
- `size_ml`
- `size_code`
- `mrp` using an appropriate decimal type
- `currency`, default `INR`
- Nullable `image_key`
- `source_date`
- `source_page`
- `active`
- Creation and update timestamps

Store codes as text to preserve leading zeros. Validate positive sizes and non-negative prices. Do not deduplicate using product name and size alone: different source product codes can share these values.

Add appropriate indexes for category/size filtering and product-code lookup.

### Dataset extraction and import

Implement a repeatable workflow:
PDF → normalized CSV → validation → catalog import.

Requirements:
- Prefer table-aware extraction.
- Carry category headings into the appropriate rows.
- Reconstruct wrapped cells and remove repeated page headers.
- Preserve original source values for audit/debugging.
- Flag ambiguous rows instead of silently guessing.
- Validate duplicate product codes, conflicting values, missing fields and invalid numbers.
- Produce accepted/rejected row reports with reasons and summary counts.
- Make import transactional and safe to rerun.
- Upsert using `product_code`.
- Do not erase existing image mappings during a price/data reimport.
- Do not automatically delete or deactivate items absent from a later input.
- Keep schema migrations separate from seed imports.
- If the PDF is unavailable, build the importer and document where to place the file; do not fabricate an extracted dataset.

## 2. Image mapping and S3

Use this object-key convention:

catalog/whisky/blenders-pride.jpeg
catalog/whisky/royal-stag.jpg
catalog/whisky/sterling-reserve-b10.jpeg
catalog/brandy/mansion-house.jpg
catalog/brandy/morpheus-xo.jpg
catalog/rum/old-monk.jpg
catalog/vodka/magic-moments-green-apple.jpg
catalog/beer/kingfisher-ultra.jpg

Actual extensions must match the supplied files.

Several sizes of the same product may share one image. Different editions/flavours should remain separately mapped.

Implement a small editable image-mapping CSV or YAML file. Allow mapping by category and brand code, with optional product-code overrides. Use explicit mappings rather than fuzzy name matching. Preserve unmapped items and display a generic placeholder.

Store S3 object keys, not image bytes or expiring URLs, in PostgreSQL.

Support two image modes:
- Local development: serve supplied files from a local static image path.
- AWS: generate short-lived presigned GET URLs for objects in a private S3 bucket using the AWS SDK default credential chain.

Do not hardcode AWS keys or make the bucket public. The later EKS deployment will use pod-level IAM permissions.

## 3. Catalog APIs

Implement:
- `GET /api/catalog/items`
- `GET /api/catalog/items/{id}`
- `GET /api/catalog/categories`
- `GET /api/catalog/sizes?category=whisky`

The list endpoint must support:
- Category
- Size in ml
- Product-name search
- Pagination with a bounded page size
- Allowlisted sorting by name, size or price

Use parameterized queries/JPA safely. Explain that size filtering uses WHERE and sorting uses ORDER BY; there is no SIZE BY clause.

Return clear JSON, including the image URL or placeholder reference.

## 4. Orders database

Create `orders` and `order_items` tables.

Orders should include:
- UUID order ID
- Unique client-supplied idempotency key
- Request fingerprint for detecting conflicting key reuse
- Demo customer reference
- Status
- Total amount and currency
- Creation and update timestamps

Order items should include:
- Order ID
- Catalog item ID and product-code snapshot
- Product-name snapshot
- Size snapshot
- Positive quantity
- Unit-price snapshot
- Line total

Do not create cross-database foreign keys. Order-item references to the local orders table should use normal foreign keys.

Orders must retain purchased names and prices even after catalog data changes. Do not trust client-supplied prices or totals.

## 5. Order workflow and APIs

Implement:
- `POST /api/orders`
- `GET /api/orders/{id}`

The creation request includes an `Idempotency-Key` header, a demo customer reference and item IDs/quantities.

Workflow:
1. Validate request quantities and items.
2. Retrieve current item details through the catalog API; never read the catalog database directly.
3. Reject inactive or unavailable catalog items.
4. Calculate totals on the server using decimal arithmetic.
5. Save the order and item snapshots atomically.
6. Return the created order.

A retry with the same key and same payload must return the existing order. Reusing the key with a different payload must return a conflict. Handle concurrent duplicate requests using a database uniqueness constraint.

Use a configurable timeout for catalog calls and return a clear error when catalog is unavailable.

This first draft excludes inventory reservations, payment processing and SQS. Use an honest initial order status such as `CREATED`; do not imply stock or payment has been confirmed. Document extension points for adding those components later.

## 6. DevOps readiness

Provide:
- A multi-stage Dockerfile for each service
- Docker Compose for PostgreSQL and both services
- Separate database initialization/users
- Environment-based configuration
- An `.env.example` with safe local examples
- Health/readiness endpoints suitable for later Kubernetes probes
- Prometheus metrics endpoints
- Structured logs with request/correlation IDs
- No passwords, tokens or presigned URLs in logs
- Sensible connection-pool limits
- A one-off import command/container that can later become a Kubernetes Job
- A minimal static placeholder image
- A `.gitignore`

Do not run data import automatically whenever an application replica starts.

## 7. Verification and documentation

Add focused tests for:
- Dataset validation and rerunnable imports
- Image-mapping precedence and preservation
- Category/size filtering
- Server-side order-price calculation
- Price snapshots surviving catalog changes
- Idempotency, including conflicting payloads

Provide a README with:
1. Architecture and repository structure
2. Exact local startup commands
3. Schema migration and dataset-import commands
4. Image-folder and mapping instructions
5. Sample curl requests and expected responses
6. How to change database endpoints to private RDS
7. Required future S3 IAM access
8. Known limitations and next steps for EKS/Helm/SQS/inventory

Implement the working draft rather than returning only a plan. Run available checks and clearly report what passed and what could not be verified. Keep all AWS provisioning and deployment disabled.
## 8. Find, download and map 15–20 product images

Search Google Images and follow the results to their source pages to find **15–20 product images matching brands and editions actually present in the supplied PDF**.

- Count any images I already supplied toward the 15–20 total.
- Prefer official manufacturer/brand sources or sources that permit reuse. Record the source URL and any available license information; Google search results alone do not grant reuse rights.
- Prioritize coverage across the categories present in the dataset.
- Match the product edition/flavour carefully. Do not substitute Sterling Reserve B7 for B10 or a different Magic Moments flavour.
- Download actual image files, not Google result-page links. Avoid hotlinking, watermarked images and bypassing access restrictions.
- Where a suitable image cannot be obtained, retain a generic placeholder and report the missing mapping.

Save images locally using a structure such as:

assets/catalog/whisky/sterling-reserve-b10.jpeg
assets/catalog/brandy/mansion-house.jpg
assets/catalog/rum/old-monk.jpg
assets/catalog/beer/kingfisher-ultra.jpg

Use lowercase names and hyphens, preserving the actual image format. Validate that each downloaded file is a readable image.

Create an image manifest containing:
- Local file path
- Intended S3 object key, beginning with `catalog/`
- Source URL
- License/reuse information, if available
- Category
- Exact product name/edition
- Matching brand code
- Optional product-code overrides

Map these images to `catalog_items.image_key` through the repeatable mapping/import process. Reuse one matching product image across bottle sizes unless size-specific images are available. Product-code overrides take precedence over broader brand mappings.

**Do not store image bytes in the catalog database.** Keep files in the local assets folder for this draft and store only their intended S3 object keys in PostgreSQL. Make local image URLs work immediately.

Provide an optional S3 upload command for later use, but do not upload to AWS automatically. Summarize the downloaded images, mapped catalog rows, unmapped items and any edition mismatches requiring review.