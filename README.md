# Codoc in Vecdraw

A collaborative vector editor similar to Google Drawings, built with [Reflex](https://reflex.dev/).

## Overview

Codoc in Vecdraw brings the power of vector graphic editing to the web with a focus on simplicity and collaboration. Whether you are brainstorming ideas, creating technical diagrams, or just doodling, Codoc provides a shared space for creativity.

### Application Interface
![Application Interface](docs/images/current_demo.jpg)
*A clean, intuitive interface with essential vector tools including rectangles, ellipses, lines, text, and freehand drawing.*

### Real-time Collaboration
![Collaboration Concept](docs/images/current_demo_concept.jpg)
*Share your workspace instantly via a room link and collaborate with others in real-time.*

## Features

- **Vector Drawing**: Create and manipulate shapes on an infinite canvas.
- **Real-time Collaboration**: Share your drawing session with others via room links.
- **Interactive UI**: Toolbar for selecting tools and a properties panel for adjusting shape attributes.

## Prerequisites

- Python 3.10 or higher
- [Poetry](https://python-poetry.org/) for dependency management

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/milochen0418/codoc_in_vecdraw.git
   cd codoc_in_vecdraw
   ```

2. Install dependencies:
   ```bash
   poetry install
   ```

## Running the Application

Start the development server:

```bash
poetry run reflex run
```

The application will be available at [http://localhost:3000](http://localhost:3000).

## Testing

This project uses [Playwright](https://playwright.dev/python/) for end-to-end testing.

### Prerequisites

Install Playwright browsers:

```bash
poetry run playwright install
```

### Running Tests

We provide a helper script `run_test_suite.sh` that handles the server lifecycle (starts the server in the background, runs the test, and cleans up afterwards).

To run the default test (image upload debug):

```bash
bash run_test_suite.sh
```

To run a specific test case:

```bash
bash run_test_suite.sh debug_image/run_test.py
```

### Adding New Test Cases

Test cases are located in the `testcases/` directory. To add a new test case:

1. Create a new directory under `testcases/` (e.g., `testcases/my_feature/`).
2. Create a Python script (e.g., `run_test.py`) inside that directory.
3. Use the `run_test_suite.sh` script to execute it:

```bash
bash run_test_suite.sh my_feature/run_test.py
```
