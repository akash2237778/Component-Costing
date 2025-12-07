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
			squaring_rate_sqinch REAL DEFAULT 4.0,
			ht_rate REAL DEFAULT 40.0
		);`,
		`CREATE TABLE IF NOT EXISTS materials (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			name TEXT NOT NULL,
			density_factor REAL, 
			rate_per_kg REAL
		);`,
		// Added SHAPE column
		`CREATE TABLE IF NOT EXISTS component_templates (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			name TEXT NOT NULL,
			shape TEXT DEFAULT 'Cuboid', -- Cuboid, Cylindrical, Fixed
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
	DB.Exec(`INSERT OR IGNORE INTO settings (id, cnc_rate_hourly, wirecut_rate_mm, squaring_rate_sqinch, ht_rate) 
             VALUES (1, 500.0, 0.25, 4.0, 40.0)`)

	var matCount int
	DB.QueryRow("SELECT count(*) FROM materials").Scan(&matCount)
	if matCount == 0 {
		DB.Exec("INSERT INTO materials (name, density_factor, rate_per_kg) VALUES ('D2 (HCHCr)', 0.00000785, 350.0)")
		DB.Exec("INSERT INTO materials (name, density_factor, rate_per_kg) VALUES ('D3', 0.00000785, 250.0)")
		DB.Exec("INSERT INTO materials (name, density_factor, rate_per_kg) VALUES ('Mild Steel (MS)', 0.00000785, 70.0)")
		DB.Exec("INSERT INTO materials (name, density_factor, rate_per_kg) VALUES ('EN31', 0.00000785, 120.0)")
	}

	// 3. Seed Components (FULL LIST)
	var compCount int
	DB.QueryRow("SELECT count(*) FROM component_templates").Scan(&compCount)
	if compCount == 0 {
		// Format: Name, Shape
		components := []struct {
			Name  string
			Shape string
		}{
			{"TOP PLATE", "Cuboid"},
			{"STRIPPER HOUSING", "Cuboid"},
			{"PARALLEL", "Cuboid"},
			{"DIE PLATE", "Cuboid"},
			{"DIE BACK PLATE", "Cuboid"},
			{"PUNCH PLATE", "Cuboid"},
			{"PUNCH BACK PLATE", "Cuboid"},
			{"STRIPPER PLATE", "Cuboid"},
			{"SCRAP CUTTER", "Cuboid"},
			{"NEST PLATE", "Cuboid"},
			{"SLEEVE PAD", "Cuboid"},
			{"PLUNGER PAD", "Cuboid"},
			{"PUNCH PACKING-1 (STATOR BLANK)", "Cuboid"},
			{"PUNCH PACKING-2 (ROTOR BLANK)", "Cuboid"},
			{"PUNCH BLOCK-1 (SLOT+ID)", "Cuboid"},
			{"PUNCH BLOCK-2 (STATOR BLANK)", "Cuboid"},
			{"PUNCH BLOCK-3 (ROTOR BLANK)", "Cuboid"},
			{"DIE BLOCK-1 (STATOR+ROTOR SLOT)", "Cuboid"},
			{"DIE BLOCK-2 (STATOR SLOT)", "Cuboid"},
			{"DIE BLOCK-3 (ROTOR SLOT)", "Cuboid"},
			{"DIE BLOCK-4 (ROTOR ID)", "Cuboid"},
			{"DIE BLOCK-5 (ROTOR BLANK)", "Cuboid"},
			{"PILLAR BASE", "Cylindrical"},
			{"BUSH STRIPPER", "Cylindrical"},
			{"BUSH TOP", "Cylindrical"},
			{"BUSH PILLAR", "Cylindrical"},
			{"TIKKI TOP", "Cylindrical"},
			{"PILLAR", "Cylindrical"},
			{"TIKKI BOTTOM", "Cylindrical"},
			{"BASE RING (STATOR BLANK)", "Cylindrical"},
			{"ROTOR HOUSING", "Cylindrical"},
			{"BEARING REST RING", "Cylindrical"},
			{"PILOT ROLLER", "Cylindrical"},
			{"DOWELL BUSH (BASE)", "Cylindrical"},
			{"DOWELL BUSH (TOP)", "Cylindrical"},
			{"DOWELL BUSH (STRIPPER)", "Cylindrical"},
			{"DOWELL PIN (TOP)", "Cylindrical"},
			{"DOWELL PIN (STRIPPER)", "Cylindrical"},
			{"PLUNGER SET", "Cylindrical"},
			{"DEAD BUTTON-1 (BASE+STRIPPER)", "Cylindrical"},
			{"DEAD BUTTON-2 (BASE+TOP)", "Cylindrical"},
			{"DIE RING-1 (ROTOR SLOT)", "Cylindrical"},
			{"DIE RING-2 (ROTOR SLOT)", "Cylindrical"},
			{"DIE RING-3 (ROTOR BLANK)", "Cylindrical"},
			{"DIE RING-4 (ROTOR ID)", "Cylindrical"},
			{"DIE RING-5 (ROTOR ID)", "Cylindrical"},
			{"DIE RING-6 (ROTOR ID)", "Cylindrical"},
			{"DIE RING-7 (STATOR SLOT)", "Cylindrical"},
			{"DIE RING-8 (STATOR BLANK)", "Cylindrical"},
			{"CLITTING DIE INSERT (OD ONLY)", "Cylindrical"},
			{"PILOT PIERCING BUSH (OD ONLY)", "Cylindrical"},
			{"PIERCING BUSH (OD ONLY)", "Cylindrical"},
			{"ROTOR BLANK PUNCH", "Cylindrical"},
			{"STATOR BLANK PUNCH", "Cylindrical"},
			{"ROTOR ID PUNCH-1", "Cylindrical"},
			{"ROTOR ID PUNCH-2", "Cylindrical"},
			{"ROTOR ID PUNCH-3", "Cylindrical"},
			{"SLOT PUNCH-1 (ROTOR)", "Cylindrical"},
			{"SLOT PUNCH-2 (ROTOR)", "Cylindrical"},
			{"SLOT PUNCH-3 (STATOR)", "Cylindrical"},
			{"CLITTING PUNCH", "Cylindrical"},
			{"PILOT PIERCING PUNCH", "Cylindrical"},
			{"PIERCING PUNCH", "Cylindrical"},
			{"NOTCHING INSERT (STATOR)", "Cylindrical"},
			{"NOTCHING INSERT (ROTOR)", "Cylindrical"},
			{"NOTCHING PUNCH (STATOR)", "Cylindrical"},
			{"NOTCHING PUNCH (ROTOR)", "Cylindrical"},
			{"LIFTER PIN (STATOR)", "Cylindrical"},
			{"LIFTER PIN (ROTOR)", "Cylindrical"},
			{"SLEEVE", "Cylindrical"},
			{"SPRING-1", "Cylindrical"},
			{"SPRING-2", "Cylindrical"},
			{"SPRING-3 (PILOT)", "Cylindrical"},
			{"GRUB SCREW", "Cylindrical"},
			{"BALL CAGE (BASE)", "Cylindrical"},
			{"BALL CAGE (STRIPPER)", "Cylindrical"},
			{"CYLINDER UNIT", "Fixed"},
			{"MTL.", "Fixed"},
			{"BEARING SET", "Fixed"},
		}

		stmt, _ := DB.Prepare("INSERT INTO component_templates (name, shape, display_order) VALUES (?, ?, ?)")
		for i, c := range components {
			stmt.Exec(c.Name, c.Shape, i+1)
		}
	}
}
