import java.util.Scanner;

public class BusBooking {
    public static void main(String[] args) {

        Scanner sc = new Scanner(System.in);

        String passengerName;
        int totalSeats = 40;
        int bookedSeats = 10;
        int availableSeats = totalSeats - bookedSeats;
        int seats;
        int fare = 50;

        System.out.println("PUBLIC TRANSPORT BOOKING");
        System.out.print("Enter Passenger Name: ");
        passengerName = sc.nextLine();

        System.out.println("Available Seats: " + availableSeats);

        System.out.print("Enter Number of Seats: ");
        seats = sc.nextInt();

        if (seats > 0 && seats <= availableSeats) {
            int totalFare = seats * fare;

            bookedSeats += seats;
            availableSeats -= seats;

            System.out.println("\nBOOKING CONFIRMED");
            System.out.println("Passenger: " + passengerName);
            System.out.println("Seats Booked: " + seats);
            System.out.println("Total Fare: Rs." + totalFare);
            System.out.println("Remaining Seats: " + availableSeats);
        } else {
            System.out.println("Booking Failed: Invalid Seat Count");
        }

        sc.close();
    }
}