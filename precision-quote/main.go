package main

import (
	"precision-quote/database"
	"precision-quote/handlers"
	"precision-quote/middleware"

	"github.com/gin-contrib/sessions"
	"github.com/gin-contrib/sessions/cookie"
	"github.com/gin-gonic/gin"
)

func main() {
	database.InitDB()
	r := gin.Default()
	r.LoadHTMLGlob("templates/*")

	// Session Store
	store := cookie.NewStore([]byte("secret"))
	r.Use(sessions.Sessions("mysession", store))

	// Public Routes
	r.GET("/login", handlers.ShowLogin)
	r.POST("/login", handlers.Login)
	r.GET("/logout", handlers.Logout)

	// Protected Routes
	authorized := r.Group("/")
	authorized.Use(middleware.AuthRequired())
	{
		authorized.GET("/", handlers.ShowDashboard)
		authorized.POST("/calculate", handlers.Calculate)
		authorized.GET("/component/add", handlers.AddRow)
		authorized.DELETE("/component/remove", handlers.RemoveRow)

		// Admin Routes
		admin := authorized.Group("/settings")
		admin.Use(middleware.AdminRequired())
		{
			admin.GET("", handlers.ShowSettings)
			admin.POST("/global", handlers.UpdateGlobal)
			admin.POST("/material/update", handlers.UpdateMaterial)
			admin.POST("/material/add", handlers.AddMaterial)
		}
	}

	r.Run(":8080")
}
