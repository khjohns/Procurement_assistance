# Database Setup Scripts

This directory contains scripts for setting up and managing the project's database.

## `run_db_setup.py`

This Python script can both reset and verify the database.

### Prerequisites

1.  **`.env` file:** Ensure you have a `.env` file in the root of the project.
2.  **`DATABASE_URL`:** The `.env` file must contain a valid `DATABASE_URL` for your Supabase or PostgreSQL database.

### Usage

The script now accepts an argument to determine its action: `setup` or `verify`.

#### To Reset and Set Up the Database

This will run `reset_database.sql`, which drops all existing tables and functions and recreates them.

```bash
python scripts/setup/run_db_setup.py setup
```

#### To Verify the Database Setup

This will run `verify_database.sql`, which performs a series of `SELECT` queries to check that tables, functions, and permissions are configured correctly. It will print the results of each check to the console.

```bash
python scripts/setup/run_db_setup.py verify
```