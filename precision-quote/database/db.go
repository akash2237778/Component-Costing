package database

import (
	"database/sql"
	"io/ioutil"
	"log"

	_ "github.com/mattn/go-sqlite3"
	"golang.org/x/crypto/bcrypt"
	"gopkg.in/yaml.v3"
)

var DB *sql.DB

// --- YAML CONFIG STRUCTS ---
type UserConfig struct {
	Users []struct {
		Username string `yaml:"username"`
		Password string `yaml:"password"`
		Role     string `yaml:"role"`
	} `yaml:"users"`
}

type MaterialConfig struct {
	Materials []struct {
		Name    string  `yaml:"name"`
		Density float64 `yaml:"density"`
		Rate    float64 `yaml:"rate"`
	} `yaml:"materials"`
}

type ComponentConfig struct {
	Components []struct {
		Name  string `yaml:"name"`
		Shape string `yaml:"shape"`
	} `yaml:"components"`
}

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
		`CREATE TABLE IF NOT EXISTS users (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			username TEXT NOT NULL UNIQUE,
			password_hash TEXT NOT NULL,
			role TEXT DEFAULT 'OPERATOR'
		);`,
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
		`CREATE TABLE IF NOT EXISTS component_templates (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			name TEXT NOT NULL,
			shape TEXT DEFAULT 'Cuboid',
			display_order INTEGER
		);`,
		// UPDATED QUOTES TABLE FOR VERSIONING
		`CREATE TABLE IF NOT EXISTS quotes (
			id INTEGER PRIMARY KEY AUTOINCREMENT, -- Internal ID (Unique for every version)
			quote_number INTEGER,                 -- Public ID (Shared by all versions of same quote)
			version INTEGER DEFAULT 1,            -- Version number (1, 2, 3...)
			customer_name TEXT,
			tool_name TEXT,
			total_cost REAL,
			created_by TEXT,
			created_at DATETIME DEFAULT CURRENT_TIMESTAMP
		);`,
		`CREATE TABLE IF NOT EXISTS quote_items (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			quote_id INTEGER,                     -- Links to quotes.id (Internal ID)
			component_name TEXT,
			shape TEXT,
			material_id INTEGER,
			length REAL,
			width REAL,
			height REAL,
			manual_price REAL,
			quantity INTEGER,
			final_cost REAL,
			include_squaring BOOLEAN,
			include_ht BOOLEAN,
			FOREIGN KEY(quote_id) REFERENCES quotes(id)
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
	// 1. SEED SETTINGS
	DB.Exec(`INSERT OR IGNORE INTO settings (id, cnc_rate_hourly, wirecut_rate_mm, squaring_rate_sqinch, ht_rate) 
             VALUES (1, 500.0, 0.25, 4.0, 40.0)`)

	// 2. SEED USERS FROM YAML
	var userCount int
	DB.QueryRow("SELECT count(*) FROM users").Scan(&userCount)
	if userCount == 0 {
		data, err := ioutil.ReadFile("users.yaml")
		if err == nil {
			var config UserConfig
			yaml.Unmarshal(data, &config)
			for _, u := range config.Users {
				hash, _ := bcrypt.GenerateFromPassword([]byte(u.Password), bcrypt.DefaultCost)
				DB.Exec("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", u.Username, string(hash), u.Role)
			}
		}
	}

	// 3. SEED MATERIALS
	var matCount int
	DB.QueryRow("SELECT count(*) FROM materials").Scan(&matCount)
	if matCount == 0 {
		data, err := ioutil.ReadFile("materials.yaml")
		if err == nil {
			var config MaterialConfig
			yaml.Unmarshal(data, &config)
			for _, m := range config.Materials {
				DB.Exec("INSERT INTO materials (name, density_factor, rate_per_kg) VALUES (?, ?, ?)", m.Name, m.Density, m.Rate)
			}
		} else {
			DB.Exec("INSERT INTO materials (name, density_factor, rate_per_kg) VALUES ('D2 (HCHCr)', 0.00000785, 350.0)")
		}
	}

	// 4. SEED COMPONENTS
	var compCount int
	DB.QueryRow("SELECT count(*) FROM component_templates").Scan(&compCount)
	if compCount == 0 {
		data, err := ioutil.ReadFile("components.yaml")
		if err == nil {
			var config ComponentConfig
			yaml.Unmarshal(data, &config)
			stmt, _ := DB.Prepare("INSERT INTO component_templates (name, shape, display_order) VALUES (?, ?, ?)")
			for i, c := range config.Components {
				stmt.Exec(c.Name, c.Shape, i+1)
			}
		} else {
			DB.Exec("INSERT INTO component_templates (name, shape, display_order) VALUES ('TOP PLATE', 'Cuboid', 1)")
		}
	}
}
