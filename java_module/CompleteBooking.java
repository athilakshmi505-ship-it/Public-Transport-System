import java.sql.*;
import java.util.Scanner;

public class CompleteBooking {

    static final String URL =
        "jdbc:postgresql://localhost:5432/public_transport_db";
    static final String USER = "postgres";
    static final String PASSWORD = "Athi@Vcet";

    static Scanner sc = new Scanner(System.in);

    public static void main(String[] args) {

        while (true) {

            System.out.println("\nPUBLIC TRANSPORT SYSTEM");
            System.out.println("1. Book Ticket");
            System.out.println("2. Cancel Ticket");
            System.out.println("3. Exit");
            System.out.print("Enter Choice: ");

            int choice = sc.nextInt();
            sc.nextLine();

            if (choice == 1) {
                bookTicket();
            } else if (choice == 2) {
                cancelTicket();
            } else if (choice == 3) {
                System.out.println("Thank You!");
                break;
            } else {
                System.out.println("Invalid Choice");
            }
        }

        sc.close();
    }

    static void bookTicket() {

        System.out.print("Passenger Name: ");
        String name = sc.nextLine();

        System.out.print("Phone Number: ");
        String phone = sc.nextLine();

        System.out.print("Schedule ID: ");
        int scheduleId = sc.nextInt();

        System.out.print("Number of Seats: ");
        int seats = sc.nextInt();

        if (seats <= 0 || phone.trim().isEmpty()) {
            System.out.println("Invalid Input");
            return;
        }

        try (Connection con =
             DriverManager.getConnection(URL, USER, PASSWORD)) {

            con.setAutoCommit(false);

            try {
                int available;

                String check =
                    "SELECT available_seats FROM schedules " +
                    "WHERE schedule_id=? FOR UPDATE";

                try (PreparedStatement ps =
                     con.prepareStatement(check)) {

                    ps.setInt(1, scheduleId);

                    try (ResultSet rs = ps.executeQuery()) {
                        if (!rs.next()) {
                            throw new SQLException("Schedule not found");
                        }

                        available = rs.getInt(1);

                        if (rs.wasNull() || seats > available) {
                            throw new SQLException(
                                "Not enough available seats"
                            );
                        }
                    }
                }

                int passengerId = -1;

                String find =
                    "SELECT passenger_id FROM passengers WHERE phone=?";

                try (PreparedStatement ps =
                     con.prepareStatement(find)) {

                    ps.setString(1, phone);

                    try (ResultSet rs = ps.executeQuery()) {
                        if (rs.next()) {
                            passengerId = rs.getInt(1);
                        }
                    }
                }

                if (passengerId == -1) {

                    String insert =
                        "INSERT INTO passengers " +
                        "(passenger_name, phone) VALUES (?,?)";

                    try (PreparedStatement ps =
                         con.prepareStatement(
                             insert, Statement.RETURN_GENERATED_KEYS)) {

                        ps.setString(1, name);
                        ps.setString(2, phone);
                        ps.executeUpdate();

                        try (ResultSet rs = ps.getGeneratedKeys()) {
                            if (!rs.next()) {
                                throw new SQLException("Passenger save failed");
                            }
                            passengerId = rs.getInt(1);
                        }
                    }
                }

                int bookingId;

                String booking =
                    "INSERT INTO bookings " +
                    "(passenger_id, schedule_id, seats_booked, status) " +
                    "VALUES (?,?,?,'Confirmed')";

                try (PreparedStatement ps =
                     con.prepareStatement(
                         booking, Statement.RETURN_GENERATED_KEYS)) {

                    ps.setInt(1, passengerId);
                    ps.setInt(2, scheduleId);
                    ps.setInt(3, seats);
                    ps.executeUpdate();

                    try (ResultSet rs = ps.getGeneratedKeys()) {
                        if (!rs.next()) {
                            throw new SQLException("Booking save failed");
                        }
                        bookingId = rs.getInt(1);
                    }
                }

                String update =
                    "UPDATE schedules SET available_seats = " +
                    "available_seats - ? WHERE schedule_id=?";

                try (PreparedStatement ps =
                     con.prepareStatement(update)) {

                    ps.setInt(1, seats);
                    ps.setInt(2, scheduleId);
                    ps.executeUpdate();
                }

                con.commit();

                System.out.println("\nBOOKING CONFIRMED");
                System.out.println("Passenger ID: " + passengerId);
                System.out.println("Booking ID: " + bookingId);
                System.out.println("Seats Booked: " + seats);
                System.out.println("Total Fare: Rs." + (seats * 50));
                System.out.println("Remaining Seats: " +
                                   (available - seats));

            } catch (Exception e) {
                con.rollback();
                System.out.println("Booking Failed: " + e.getMessage());
            }

        } catch (Exception e) {
            System.out.println("Database Error: " + e.getMessage());
        }
    }

    static void cancelTicket() {

        System.out.print("Enter Booking ID: ");
        int bookingId = sc.nextInt();

        try (Connection con =
             DriverManager.getConnection(URL, USER, PASSWORD)) {

            con.setAutoCommit(false);

            try {
                int scheduleId;
                int seats;

                String find =
                    "SELECT schedule_id, seats_booked FROM bookings " +
                    "WHERE booking_id=? AND status='Confirmed' " +
                    "FOR UPDATE";

                try (PreparedStatement ps =
                     con.prepareStatement(find)) {

                    ps.setInt(1, bookingId);

                    try (ResultSet rs = ps.executeQuery()) {
                        if (!rs.next()) {
                            throw new SQLException(
                                "Booking not found or already cancelled"
                            );
                        }

                        scheduleId = rs.getInt(1);
                        seats = rs.getInt(2);
                    }
                }

                String cancel =
                    "UPDATE bookings SET status='Cancelled' " +
                    "WHERE booking_id=?";

                try (PreparedStatement ps =
                     con.prepareStatement(cancel)) {

                    ps.setInt(1, bookingId);
                    ps.executeUpdate();
                }

                String restore =
                    "UPDATE schedules SET available_seats = " +
                    "available_seats + ? WHERE schedule_id=?";

                try (PreparedStatement ps =
                     con.prepareStatement(restore)) {

                    ps.setInt(1, seats);
                    ps.setInt(2, scheduleId);
                    ps.executeUpdate();
                }

                con.commit();

                System.out.println("\nTICKET CANCELLED SUCCESSFULLY");
                System.out.println("Booking ID: " + bookingId);
                System.out.println("Seats Restored: " + seats);

            } catch (Exception e) {
                con.rollback();
                System.out.println("Cancellation Failed: " + e.getMessage());
            }

        } catch (Exception e) {
            System.out.println("Database Error: " + e.getMessage());
        }
    }
}