package handlers

import (
	"database/sql"
	"net/http"

	"precision-quote/database"

	"github.com/gin-contrib/sessions"
	"github.com/gin-gonic/gin"
	"golang.org/x/crypto/bcrypt"
)

func ShowLogin(c *gin.Context) {
	c.HTML(http.StatusOK, "login.html", nil)
}

func Login(c *gin.Context) {
	username := c.PostForm("username")
	password := c.PostForm("password")

	var dbHash, role string
	var id int
	err := database.DB.QueryRow("SELECT id, password_hash, role FROM users WHERE username=?", username).Scan(&id, &dbHash, &role)

	if err == sql.ErrNoRows {
		c.HTML(http.StatusUnauthorized, "login.html", gin.H{"Error": "User not found"})
		return
	}

	if err := bcrypt.CompareHashAndPassword([]byte(dbHash), []byte(password)); err != nil {
		c.HTML(http.StatusUnauthorized, "login.html", gin.H{"Error": "Invalid Password"})
		return
	}

	session := sessions.Default(c)
	session.Set("user_id", id)
	session.Set("role", role)
	session.Set("username", username)
	session.Save()

	c.Redirect(http.StatusFound, "/")
}

func Logout(c *gin.Context) {
	session := sessions.Default(c)
	session.Clear()
	session.Save()
	c.Redirect(http.StatusFound, "/login")
}
