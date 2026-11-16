import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.Statement;

public class DBConnectionTest {
    public static void main(String[] args) {

        String url = "jdbc:postgresql://localhost:5432/public_transport_db";
        String user = "postgres";
        String password = "Athi@Vcet";

        try {
            Connection con = DriverManager.getConnection(
                url, user, password
            );

            System.out.println("Database Connected Successfully!");

            Statement st = con.createStatement();
            ResultSet rs = st.executeQuery(
                "SELECT COUNT(*) FROM buses"
            );

            if (rs.next()) {
                System.out.println("Total Buses: " + rs.getInt(1));
            }

            con.close();

        } catch (Exception e) {
            System.out.println("Connection Error: " + e.getMessage());
        }
    }
}