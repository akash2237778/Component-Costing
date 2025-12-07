package database

import (
	"database/sql"
	"log"

	_ "github.com/mattn/go-sqlite3"
)

var DB *sql.DB

func InitDB() {
	var err error
	DB, err = sql.Open("sqlite3", "./precision_quote.db")
	if err != nil {
		log.Fatal(err)
	}

	createTables()
	seedData()
}

func createTables() {
	queries := []string{
		`CREATE TABLE IF NOT EXISTS settings (
			id INTEGER PRIMARY KEY CHECK (id = 1),
			cnc_rate_hourly REAL DEFAULT 500.0,
			wirecut_rate_mm REAL DEFAULT 0.25,
			squaring_rate_sqinch REAL DEFAULT 4.0
		);`,
		`CREATE TABLE IF NOT EXISTS materials (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			name TEXT NOT NULL,
			density_factor REAL, -- kg per cubic inch
			rate_per_kg REAL
		);`,
		`CREATE TABLE IF NOT EXISTS component_templates (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			name TEXT NOT NULL,
			display_order INTEGER
		);`,
	}

	for _, query := range queries {
		_, err := DB.Exec(query)
		if err != nil {
			log.Println("Error creating table:", err)
		}
	}
}

func seedData() {
	// 1. Seed Settings (Your specific rates)
	DB.Exec("INSERT OR IGNORE INTO settings (id, cnc_rate_hourly, wirecut_rate_mm, squaring_rate_sqinch) VALUES (1, 500.0, 0.25, 4.0)")

	// 2. Seed Materials
	// Note: 1 inch³ steel ≈ 0.128 kg. D2 is slightly denser.
	// Rate per KG is an estimate, you can update this in DB later.
	var matCount int
	DB.QueryRow("SELECT count(*) FROM materials").Scan(&matCount)
	if matCount == 0 {
		DB.Exec("INSERT INTO materials (name, density_factor, rate_per_kg) VALUES ('D2 (HCHCr)', 0.128, 350.0)")
		DB.Exec("INSERT INTO materials (name, density_factor, rate_per_kg) VALUES ('D3', 0.128, 250.0)")
		DB.Exec("INSERT INTO materials (name, density_factor, rate_per_kg) VALUES ('Mild Steel (MS)', 0.128, 70.0)")
		DB.Exec("INSERT INTO materials (name, density_factor, rate_per_kg) VALUES ('EN31', 0.128, 120.0)")
	}

	// 3. Seed Components (Your partial list)
	var compCount int
	DB.QueryRow("SELECT count(*) FROM component_templates").Scan(&compCount)
	if compCount == 0 {
		components := []string{
			"BOTTOM PLATE", "TOP PLATE", "ST. HOUSING", "PARALLEL DIE PLATE",
			"DIE BACK PLATE", "PUNCH PLATE", "PUNCH BACK PLATE", "ST. PLATE",
			"SCRAP CUTTER", "NEST PLATE", "SLEEVE PAD",
		}
		stmt, _ := DB.Prepare("INSERT INTO component_templates (name, display_order) VALUES (?, ?)")
		for i, name := range components {
			stmt.Exec(name, i+1)
		}
	}
}