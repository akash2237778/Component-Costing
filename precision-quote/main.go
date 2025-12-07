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

	store := cookie.NewStore([]byte("secret"))
	r.Use(sessions.Sessions("mysession", store))

	r.GET("/login", handlers.ShowLogin)
	r.POST("/login", handlers.Login)
	r.GET("/logout", handlers.Logout)

	authorized := r.Group("/")
	authorized.Use(middleware.AuthRequired())
	{
		authorized.GET("/", handlers.ShowDashboard)
		authorized.POST("/calculate", handlers.Calculate)
		authorized.GET("/component/add", handlers.AddRow)
		authorized.DELETE("/component/remove", handlers.RemoveRow)

		// QUOTE ROUTES
		authorized.POST("/quotes/save", handlers.SaveQuote)
		authorized.GET("/history", handlers.ShowHistory)
		authorized.GET("/quotes/load/:id", handlers.LoadQuote) // NEW

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
