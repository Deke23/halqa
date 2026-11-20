# Third-party notices

This file lists the direct open-source dependencies of this project, with their versions and licences as installed on the build date, 2026-11-20. Transitive dependencies are resolved by pip and npm at install time, and they can be listed with `pip list` (or `pip show`) for the Python packages and `npm ls --all` for the JavaScript packages. The base container images are `python:3.12-slim` and `node:22-alpine`.

## Python (backend/requirements.txt)

| Package | Version | Licence | URL |
| --- | --- | --- | --- |
| fastapi | 0.164.0 | MIT | https://github.com/fastapi/fastapi |
| uvicorn | 0.54.0 | BSD-3-Clause | https://uvicorn.dev/ |
| sqlalchemy | 2.1.9 | MIT | https://www.sqlalchemy.org |
| pydantic | 2.14.3 | MIT | https://github.com/pydantic/pydantic |
| pydantic-settings | 2.16.3 | MIT | https://github.com/pydantic/pydantic-settings |
| fhir.resources | 8.3.0 | BSD license | https://github.com/nazrulworld/fhir.resources |
| pyyaml | 6.0.3 | MIT | https://pyyaml.org/ |
| pyjwt | 2.15.1 | MIT | https://github.com/jpadilla/pyjwt |
| numpy | 2.5.5 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | https://numpy.org |
| httpx | 0.28.1 | BSD-3-Clause | https://github.com/encode/httpx |
| psycopg | 3.3.9 | LGPL-3.0-only | https://psycopg.org/ |
| pytest | 9.2.0 | MIT | https://docs.pytest.org/en/latest/ |

## JavaScript (frontend/package.json)

| Package | Version | Licence | Type | URL |
| --- | --- | --- | --- | --- |
| @fontsource/ibm-plex-mono | 5.3.0 | OFL-1.1 | runtime | https://fontsource.org/fonts/ibm-plex-mono |
| @fontsource/ibm-plex-sans | 5.3.0 | OFL-1.1 | runtime | https://fontsource.org/fonts/ibm-plex-sans |
| @fontsource/ibm-plex-sans-arabic | 5.3.0 | OFL-1.1 | runtime | https://fontsource.org/fonts/ibm-plex-sans-arabic |
| @tanstack/react-query | 5.108.0 | MIT | runtime | https://tanstack.com/query |
| i18next | 27.1.5 | MIT | runtime | https://www.i18next.com |
| react | 19.3.1 | MIT | runtime | https://react.dev/ |
| react-dom | 19.3.1 | MIT | runtime | https://react.dev/ |
| react-i18next | 18.0.2 | MIT | runtime | https://github.com/i18next/react-i18next |
| react-router-dom | 7.18.5 | MIT | runtime | https://github.com/remix-run/react-router |
| recharts | 3.11.0 | MIT | runtime | https://github.com/recharts/recharts |
| @tailwindcss/vite | 4.3.5 | MIT | dev | https://tailwindcss.com |
| @types/node | 26.6.6 | MIT | dev | https://github.com/DefinitelyTyped/DefinitelyTyped/tree/master/types/node |
| @types/react | 19.3.0 | MIT | dev | https://github.com/DefinitelyTyped/DefinitelyTyped/tree/master/types/react |
| @types/react-dom | 19.3.0 | MIT | dev | https://github.com/DefinitelyTyped/DefinitelyTyped/tree/master/types/react-dom |
| @vitejs/plugin-react | 6.3.0 | MIT | dev | https://github.com/vitejs/vite-plugin-react/tree/main/packages/plugin-react#readme |
| openapi-typescript | 7.13.0 | MIT | dev | https://openapi-ts.dev |
| tailwindcss | 4.3.5 | MIT | dev | https://tailwindcss.com |
| typescript | 5.9.3 | Apache-2.0 | dev | https://www.typescriptlang.org/ |
| vite | 8.3.8 | MIT | dev | https://vite.dev |

The three @fontsource packages bundle the IBM Plex Sans, IBM Plex Sans Arabic and IBM Plex Mono typefaces, which are self-hosted by the application under the SIL Open Font License 1.1.

## How to regenerate

Run these from the repository root. The Python script needs the dev container, and the JavaScript script needs `frontend/node_modules` to be installed.

```
MSYS_NO_PATHCONV=1 wsl -e bash /mnt/d/Projects/Hackathon/dev/run.sh py /srv/dev/licenses_py.py
node dev/licenses_js.mjs
```
