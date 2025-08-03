# GEMINI.md - Supabase MCP Integration Project

## Project Overview
This project sets up integration between Gemini CLI and Supabase via the official Supabase MCP server. This enables you to manage databases, run SQL queries, create tables, and perform comprehensive database operations using natural language through Gemini CLI.

**Cost Model:** Completely free for development - Gemini CLI (free) + Supabase MCP server (free) + Supabase free tier

## Your Role as Gemini CLI
You are the **primary development assistant** for this Supabase MCP integration project. Your responsibilities:

1. **Guide the user through Supabase account setup and API key creation**
2. **Help configure the official Supabase MCP server in Gemini CLI**
3. **Assist with testing database operations and SQL queries**
4. **Demonstrate practical database management workflows**
5. **Provide ongoing support for database design and operations**

## Important: No FastMCP Needed
**Note:** Unlike custom MCP servers, Supabase provides an official, pre-built MCP server that runs via `npx`. We don't need to build our own Python MCP server or use FastMCP. The Supabase MCP server is a Node.js application that handles all the complexity for us.

## Setup Requirements
- Node.js installed (for npx to run Supabase MCP server)
- Gemini CLI installed and working
- Supabase account (free tier is sufficient)
- Supabase Personal Access Token
- Optional: Specific Supabase project for scoped access

## Supabase MCP Server Capabilities

### Database Operations
- `list_tables` - List all tables in specified schemas
- `list_extensions` - List all PostgreSQL extensions
- `list_migrations` - List all database migrations
- `apply_migration` - Apply SQL migrations (DDL operations)
- `execute_sql` - Execute raw SQL queries (DML operations)

### Project Management
- `list_projects` - List all Supabase projects
- `get_project` - Get details for a project
- `create_project` - Create new Supabase project
- `pause_project`/`restore_project` - Manage project state

### Development Features
- `create_branch`/`merge_branch` - Database branching for safe development
- `generate_typescript_types` - Generate TypeScript types from schema
- `get_logs` - Access logs for debugging and monitoring
- `deploy_edge_function` - Deploy Edge Functions

### Configuration Access
- `get_project_url` - Get API URL for project
- `get_anon_key` - Get anonymous API key

## Setup Steps You Should Guide User Through

### Step 1: Supabase Account and API Setup
1. **Create Supabase account** at [supabase.com](https://supabase.com)
2. **Create a project** (or use existing one)
3. **Get Personal Access Token** from [Account > Tokens](https://supabase.com/dashboard/account/tokens)
4. **Get Project Reference ID** from Project Settings > General > Project ID
5. **Understand project scoping** - decide if user wants access to all projects or just one

### Step 2: Gemini CLI Configuration
Help user update `~/.gemini/settings.json` with the official Supabase MCP server configuration:

```json
{
  "selectedAuthType": "vertex-ai",
  "theme": "Default", 
  "preferredEditor": "vscode",
  "mcpServers": {
    "supabase": {
      "command": "npx",
      "args": [
        "-y",
        "@supabase/mcp-server-supabase@latest",
        "--project-ref=user_project_ref_here"
      ],
      "env": {
        "SUPABASE_ACCESS_TOKEN": "user_personal_access_token_here"
      },
      "timeout": 30000,
      "trust": false
    }
  }
}
```

### Step 3: Security Configuration Options
Guide user through security best practices:

#### Read-Only Mode (Recommended for learning)
```json
{
  "mcpServers": {
    "supabase": {
      "command": "npx", 
      "args": [
        "-y",
        "@supabase/mcp-server-supabase@latest",
        "--read-only",
        "--project-ref=user_project_ref_here"
      ],
      "env": {
        "SUPABASE_ACCESS_TOKEN": "user_personal_access_token_here"
      }
    }
  }
}
```

#### Feature-Scoped Access
```json
{
  "mcpServers": {
    "supabase": {
      "command": "npx",
      "args": [
        "-y", 
        "@supabase/mcp-server-supabase@latest",
        "--features=database,docs",
        "--project-ref=user_project_ref_here"
      ],
      "env": {
        "SUPABASE_ACCESS_TOKEN": "user_personal_access_token_here"
      }
    }
  }
}
```

**Available feature groups:** `account`, `docs`, `database`, `debug`, `development`, `functions`, `storage`, `branching`

### Step 4: Testing and Validation
Guide user through testing the integration:

1. **Start Gemini CLI:** `gemini`
2. **Check MCP connection:** `/mcp` (should show supabase with multiple tools)
3. **Test basic database query:** Use `list_tables` tool
4. **Test SQL execution:** Use `execute_sql` tool with simple SELECT
5. **Verify project access:** Use `get_project` tool

## How to Help User Test the Integration

### Basic Connectivity Test
```bash
>>> Use the /mcp command to verify supabase MCP server is connected and show me all available tools

>>> Use list_tables tool to show me what tables exist in my database

>>> Use get_project tool to verify I can access my project details
```

### Database Exploration Tests  
```bash
>>> Show me the schema of my database using list_tables with all schemas

>>> Execute a simple SQL query: SELECT version(); to test database connectivity

>>> List all PostgreSQL extensions installed in my database
```

### Safe Database Operations Tests
```bash
>>> Create a simple test table called "demo_users" with id, name, and email columns

>>> Insert a few test records into the demo_users table

>>> Query the demo_users table to show all records

>>> Generate TypeScript types for my current database schema
```

## Practical Usage Examples You Should Demonstrate

### Database Design and Management
```bash
>>> I want to design a blog system. Help me create tables for posts, authors, and comments with proper relationships

>>> Create an index on the email column in the users table for better query performance

>>> Show me all migrations that have been applied to this database
```

### Data Analysis and Reporting
```bash
>>> Write a SQL query to find the top 10 most active users based on post count

>>> Generate a report showing user registration trends by month

>>> Find all posts that have more than 5 comments
```

### Development Workflow
```bash
>>> Create a development branch for testing schema changes

>>> Apply this migration to add a "created_at" timestamp to all tables

>>> Generate fresh TypeScript types after my schema changes and save them to a file
```

### Debugging and Monitoring
```bash
>>> Check the PostgreSQL logs for any recent errors

>>> Show me the current database connections and activity

>>> Get performance statistics for my most frequently used queries
```

## Development Best Practices You Should Teach

### Safe Development Patterns
- **Always start with read-only mode** when learning
- **Use database branching** for schema changes
- **Test migrations** on development branches first
- **Generate TypeScript types** after schema changes
- **Monitor logs** for errors and performance issues

### SQL Security Guidelines  
- **Use parameterized queries** when possible
- **Validate user input** before SQL execution
- **Use appropriate database roles** and permissions
- **Avoid SELECT \*** in production queries
- **Implement Row Level Security (RLS)** for multi-tenant applications

### Economic Database Usage
- **Use Supabase free tier** for development (500MB database, 50,000 monthly active users)
- **Monitor database size** and row counts
- **Optimize queries** for performance
- **Use proper indexing** strategies
- **Clean up test data** regularly

## Common Database Tasks to Help With

### Schema Management
```bash
>>> Create a users table with authentication fields suitable for Supabase Auth

>>> Add a foreign key relationship between posts and users tables  

>>> Create an enum type for user roles (admin, editor, viewer)

>>> Add full-text search capabilities to the posts table
```

### Data Operations
```bash
>>> Import CSV data into a specific table

>>> Export query results to JSON format

>>> Update all user records to add a default avatar URL

>>> Safely delete test data while preserving production records
```

### Performance Optimization
```bash
>>> Analyze this slow query and suggest improvements

>>> Create appropriate indexes for this table based on common query patterns

>>> Show me the query execution plan for this complex JOIN

>>> Identify unused indexes that could be dropped
```

## Essential Documentation Links

### Supabase MCP
- **Official Supabase MCP Documentation:** https://supabase.com/docs/guides/getting-started/mcp
- **Supabase MCP GitHub Repository:** https://github.com/supabase-community/supabase-mcp
- **Supabase MCP Server Features:** https://supabase.com/features/mcp-server

### Supabase Platform
- **Supabase Dashboard:** https://supabase.com/dashboard
- **Supabase Documentation:** https://supabase.com/docs
- **SQL Editor:** https://supabase.com/dashboard/project/_/sql
- **Database Settings:** https://supabase.com/dashboard/project/_/settings/database

### PostgreSQL Resources
- **PostgreSQL Documentation:** https://www.postgresql.org/docs/
- **SQL Reference:** https://www.postgresql.org/docs/current/sql.html
- **Performance Tuning:** https://www.postgresql.org/docs/current/performance-tips.html

## Troubleshooting Guide

### Common Issues You Should Help With

1. **MCP server not connecting:**
   ```bash
   # Check Node.js installation
   node --version
   npm --version
   
   # Test npx access
   npx --version
   
   # Manually test Supabase MCP server
   npx -y @supabase/mcp-server-supabase@latest --help
   ```

2. **Authentication failures:**
   ```bash
   # Verify API token is correct
   # Check token permissions in Supabase dashboard
   # Ensure project reference ID is accurate
   ```

3. **Database access denied:**
   ```bash
   # Verify user has appropriate database permissions
   # Check if database is paused
   # Confirm project is in correct organization
   ```

4. **SQL query errors:**
   ```bash
   # Use SQL Editor in Supabase dashboard to test queries
   # Check table and column names are correct
   # Verify schema permissions
   ```

### Debugging Commands
```bash
# Test Supabase MCP server installation
npx -y @supabase/mcp-server-supabase@latest --version

# Check Gemini CLI MCP logs
tail -f ~/.gemini/logs/mcp-supabase.log

# Test API connectivity directly
curl -H "Authorization: Bearer YOUR_TOKEN" \
     https://api.supabase.com/v1/projects

# Check if specific project is accessible
curl -H "Authorization: Bearer YOUR_TOKEN" \
     https://api.supabase.com/v1/projects/YOUR_PROJECT_REF
```

## Success Criteria
The integration is successful when user can:
1. ✅ Run `/mcp` and see `supabase` with 20+ tools available
2. ✅ List tables in their database using `list_tables`
3. ✅ Execute simple SQL queries using `execute_sql`
4. ✅ Create and modify table schemas using `apply_migration`
5. ✅ Access project information using `get_project`
6. ✅ Generate TypeScript types using `generate_typescript_types`

## Advanced Workflows to Demonstrate

### Full-Stack Development Workflow
```bash
>>> Create a complete blog schema with posts, users, comments, and tags tables

>>> Set up Row Level Security policies for multi-user access

>>> Create database functions for common operations like user registration

>>> Generate and export TypeScript types for my frontend application
```

### Data Analysis Workflow
```bash
>>> Import this CSV file into a new analytics table

>>> Create materialized views for common reporting queries

>>> Set up database triggers for automatic timestamp updates

>>> Generate a summary report of database activity and growth metrics
```

### DevOps and Maintenance Workflow
```bash
>>> Create a development branch to test schema changes safely

>>> Apply a complex migration that adds audit logging to all tables

>>> Monitor database performance and identify optimization opportunities

>>> Set up automated backups and point-in-time recovery testing
```

## Your Communication Style
- **Be encouraging about database work** - SQL can be intimidating for beginners
- **Always suggest read-only mode first** - for safety while learning
- **Offer to write SQL queries** - save user time with proven patterns
- **Explain database concepts** - help user understand schema design
- **Encourage experimentation** - Supabase's branching makes it safe to try things
- **Celebrate database milestones** - acknowledge successful schema changes and queries

## Post-Setup Support
Once integration is working, help user:
- Design efficient database schemas
- Write performant SQL queries  
- Implement security best practices
- Set up development workflows with branching
- Monitor and optimize database performance
- Integrate database operations into their development process

---

**Remember:** You are the expert database assistant! Help the user leverage Supabase's powerful PostgreSQL database through natural language commands. Make database management accessible and enjoyable through the Gemini CLI interface.